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


class RemoveEmailCommandV2(UserRelatedCommand):
    KEYWORD = "remove_email"

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
        self.email: str | None = None

    async def remove_email(self, user_id: str) -> bool:
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

        # Check if user has already an email
        params = {
            "filter[user]": mas_user_id,
        }
        user_emails = await self.admin_client.find_emails(
            self.json_report, self.failed_user_ids, user_id, params
        )
        if user_emails is None:
            return False
        if len(user_emails) != 1:
            self.json_report[user_id]["errors"].append(
                {
                    "error": f"The user [mxid={user_id}/mas_user_id={mas_user_id}] "
                    f"has no emails or have many emails : "
                    f"number of emails={len(user_emails)}.",
                    "description": user_emails,
                }
            )
            self.failed_user_ids.append(user_id)
            return False

        # Remove email for the user
        user_email_id = user_emails[0]["id"]
        email = user_emails[0]["attributes"]["email"]
        result = await self.admin_client.remove_email(
            self.json_report, self.failed_user_ids, user_email_id, user_id
        )
        if result:
            self.json_report[user_id]["description"] = (
                f"{email} has been removed for {user_id}"
            )
        return result

    @override
    async def should_execute(self) -> bool:
        args = self.command_text.split()
        if len(args) != 1:
            return False

        self.user_id = args[0]
        # TODO: validate user_id

        return is_local_user(self.user_id, self.server_name)

    @override
    async def simple_execute(self) -> bool:
        if self.user_id is None or self.email is None:
            return False
        await self.remove_email(self.user_id)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()
        logger.info(self.json_report)
        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't remove email the following users:",
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
                "You are about to reactivate the following users:",
                "",
                *[f"- {self.user_id}"],
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!remove_email @user1 user1@domain.tld`

**Purpose**:
Remove an email for a user.

**Effects**:
- remove an email for a user
- cheks if the user has only one email

**Examples**:
- `!remove_email @user-domain.tld:example.com`

NOTE : you want to use replace_email command if you want to replace an email on a user
"""
