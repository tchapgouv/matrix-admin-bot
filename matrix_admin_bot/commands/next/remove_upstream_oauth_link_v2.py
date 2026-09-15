from collections.abc import Mapping
from typing import Any, override

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.admin_client import AdminClient
from matrix_command_bot.util import get_server_name, is_local_user

logger = structlog.getLogger(__name__)


class RemoveUpstreamOauthLinkCommandV2(UserRelatedCommand):
    KEYWORD = "remove_upstream_oauth_links"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.transform_cmd_input_fct = None
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.failed_user_ids: list[str] = []
        self.user_id: str | None = None

    async def remove_upstream_oauth_links(self, user_id: str) -> bool:
        if get_server_name(user_id) != self.server_name:
            return True

        # Initialize report for user_id
        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        # Get the user from the MAS with its localpart
        mas_user_id = await self.admin_client.get_mas_user_id(
            self.json_report, self.failed_user_ids, user_id
        )
        if mas_user_id is None:
            return False

        # Find all upstream OAuth links for the user
        links = await self.admin_client.find_upstream_oauth_links(
            self.json_report, self.failed_user_ids, mas_user_id, user_id
        )
        if links is None:
            return False

        if len(links) == 0:
            self.json_report[user_id]["description"] = (
                f"No upstream OAuth links found for {user_id}"
            )
            return True

        # Remove each upstream OAuth link
        removed_links: list[str] = []
        for link in links:
            link_id = link["id"]
            result = await self.admin_client.remove_upstream_oauth_link(
                self.json_report, self.failed_user_ids, link_id, user_id
            )
            if result:
                removed_links.append(link_id)

        self.json_report[user_id]["description"] = (
            f"{len(removed_links)} upstream OAuth link(s) "
            f"removed for {user_id}"
        )
        return len(removed_links) == len(links)

    @override
    async def should_execute(self) -> bool:
        args = self.command_text.split()
        if len(args) != 1:
            return False

        self.user_id = args[0]
        return is_local_user(self.user_id, self.server_name)

    @override
    async def simple_execute(self) -> bool:
        if self.user_id is None:
            return False
        await self.remove_upstream_oauth_links(self.user_id)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()
        logger.info(self.json_report)
        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't remove upstream OAuth links of the following users:",
                    "",
                    *[f"- {user_id}" for user_id in self.failed_user_ids],
                ]
            )
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        return not self.failed_user_ids

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to remove all upstream OAuth links:",
                "",
                *[f"- {self.user_id}"],
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!remove_upstream_oauth_links @user1`

**Purpose**:
Remove all upstream OAuth links for a user.

**Effects**:
- finds all upstream OAuth links associated with the user
- deletes each link

**Examples**:
- `!remove_upstream_oauth_links @user-domain.tld:example.com`
"""
