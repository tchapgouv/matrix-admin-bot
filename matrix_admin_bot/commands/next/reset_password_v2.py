import secrets
import string
from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class ResetPasswordCommandV2(UserRelatedCommand):
    KEYWORD = "reset_password"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.failed_user_ids: list[str] = []

    async def reset_password(self, user_id: str, password: str) -> bool:
        if get_server_name(user_id) != self.server_name:
            return True

        # Initialize report for user_id
        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        # Get devices from the user in Synapse
        await self.admin_client.get_devices_from_synapse(self.json_report, user_id)

        # Get the user from the MAS with its localpart
        mas_user_id = await self.admin_client.get_mas_user_id(
            self.json_report, self.failed_user_ids, user_id
        )
        if mas_user_id is None:
            return False

        # Get all compat-sessions in MAS
        await self.admin_client.get_compat_sessions(
            self.json_report, self.failed_user_ids, mas_user_id, user_id
        )

        # Get all user-sessions in MAS
        await self.admin_client.get_user_sessions(
            self.json_report, self.failed_user_ids, mas_user_id, user_id
        )

        # Get all oauth2-sessions
        await self.admin_client.get_oauth2_sessions(
            self.json_report, self.failed_user_ids, mas_user_id, user_id
        )

        # Reset the password within the MAS
        set_password_success = await self.admin_client.set_password(
            self.json_report, self.failed_user_ids, mas_user_id, password, user_id
        )
        if not set_password_success:
            return False

        # Kill all sessions
        return await self.admin_client.kill_all_sessions(
            self.json_report, self.failed_user_ids, mas_user_id, user_id
        )

    @override
    async def simple_execute(self) -> bool:
        def randomword(length: int) -> str:
            characters = string.ascii_lowercase + string.digits
            return "".join(secrets.choice(characters) for _ in range(length))

        for user_id in self.user_ids:
            await self.reset_password(user_id, randomword(32))

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't reset the password of the following users:",
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
                "You are about to reset password of the following users with MAS:",
                "",
                *[f"- {user_id}" for user_id in self.user_ids],
                "",
                "⚠⚠ This will also log-out all of their devices!",
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!reset_password <user1> [user2] ...`

**Purpose**:
Resets a user's password to a new randomly generated one.

**Effects**:
- Logs out all sessions currently logged into the account
- Reports all sessions in the JSON report of the command

**Examples**:
- `!reset_password @user:example.com`
- `!reset_password @user1:example.com @user2:example.com`
"""
