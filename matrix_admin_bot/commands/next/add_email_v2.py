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


class AddEmailCommandV2(UserRelatedCommand):
    KEYWORD = "add_email"

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

    async def add_email(self, user_id: str, email: str) -> bool:  # noqa: PLR0911
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

        # Check if email is used
        params = {
            "filter[email]": email,
        }
        user_emails = await self.admin_client.find_emails(
            self.json_report, self.failed_user_ids, user_id, params
        )
        if user_emails is None:
            return False

        if len(user_emails) != 0:
            self.json_report[user_id]["errors"].append(
                {
                    "error": f"The email={email} is already in used.",
                    "description": user_emails,
                }
            )
            self.failed_user_ids.append(user_id)
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
        if len(user_emails) != 0:
            self.json_report[user_id]["errors"].append(
                {
                    "error": f"The user [mxid={user_id}/mas_user_id={mas_user_id}] "
                    f"has already an email : number of emails={len(user_emails)}.",
                    "description": user_emails,
                }
            )
            self.failed_user_ids.append(user_id)
            return False

        # Add email for the user
        return await self.admin_client.add_email(
            self.json_report, self.failed_user_ids, mas_user_id, user_id, email
        )

    @override
    async def should_execute(self) -> bool:
        args = self.command_text.split()
        if len(args) != 2:
            return False

        self.user_id = args[0]
        # TODO: validate user_id
        self.email = args[1]
        # TODO: validate email
        return is_local_user(self.user_id, self.server_name)

    @override
    async def simple_execute(self) -> bool:
        if self.user_id is None or self.email is None:
            return False

        await self.add_email(self.user_id, self.email)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()
        logger.info(self.json_report)
        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't add email the following users:",
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
`!add_email <mxid> <email>`

**Purpose**:
Add an email for a user.

**Effects**:
- add an email for a user
- checks the email is not already used before adding an email.
- cheks if the user has no email defined

**Examples**:
- `!add_email @user-domain.tld:example.com user@domain.tld`

NOTE : you want to use replace_email command if you want to replace an email on a user
"""
