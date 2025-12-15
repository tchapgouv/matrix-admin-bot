from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.util import get_server_name


class UnlockCommandV2(UserRelatedCommand):
    KEYWORD = "unlock"

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

    async def unlock_user(self, user_id: str) -> bool:
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

        # Unlock the user
        return await self.admin_client.unlock(
            self.json_report, self.failed_user_ids, mas_user_id, user_id
        )

    @override
    async def simple_execute(self) -> bool:
        for user_id in self.user_ids:
            await self.unlock_user(user_id)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't unlock the following users:",
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
                "You are about to unlock the following users:",
                "",
                *[f"- {user_id}" for user_id in self.user_ids],
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!unlock <user1> [user2] ...`

**Purpose**:
Unlocks Matrix accounts.

**Effects**:
- Unlock will lift restrictions on user actions that had imposed by locking.
- This DOES NOT reactivate a deactivated user, which will remain unavailable
until it is explicitly reactivated.
- Reports all sessions in the JSON report of the command

**Examples**:
- `!unlock @user:example.com`
- `!unlock @user1:example.com user2@example.com`
"""
