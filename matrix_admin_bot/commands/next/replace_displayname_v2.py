from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.util import get_server_name, is_local_user

logger = structlog.getLogger(__name__)


class ReplaceDisplayNameCommandV2(UserRelatedCommand):
    KEYWORD = "replace_displayname"

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
        self.displayname: str | None = None

    async def replace_displayname(self, user_id: str, displayname: str) -> bool:
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

        data = {
            "displayname": displayname,
        }

        resp = await self.admin_client.send_to_synapse(
            "PUT", f"/_synapse/admin/v2/users/{user_id}", data=data
        )

        if resp.status == 200:
            json_body = await resp.json()
            self.json_report[user_id] = json_body
        else:
            json_body = await resp.json()
            self.json_report[user_id].update(json_body)
            self.failed_user_ids.append(user_id)
            return False

        return True

    @override
    async def simple_execute(self) -> bool:
        if self.user_id is None or self.displayname is None:
            return False

        await self.replace_displayname(self.user_id, self.displayname)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()
        logger.info(self.json_report)
        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't replace displayname of the following users:",
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

    @override
    async def should_execute(self) -> bool:
        args = self.command_text.split(" ", 1)

        self.user_id = args[0]
        # TODO: validate user_id
        self.displayname = args[1].strip("'")
        # TODO: validate displayname
        return is_local_user(self.user_id, self.server_name)

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to replace the displayname of user:",
                "",
                *[f"- {self.user_id}"],
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!replace_displayname @user1 displaname`

**Purpose**:
Replace the displayname of a user.

**Effects**:
- Replace the displayname for a user

**Examples**:
- `!replace_displayname @user-domain.tld:example.com 'My-Display Name [domain]'`
"""
