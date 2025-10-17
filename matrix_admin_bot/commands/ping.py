from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot.commands.server_notice import USER_ALL
from matrix_command_bot.util import get_server_name, send_report
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand


class PingCommand(SimpleValidatedCommand):
    KEYWORD = "ping"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        secure_validator: IValidator = extra_config.get("secure_validator")  # pyright: ignore[reportAssignmentType]

        super().__init__(room, message, matrix_client, secure_validator, extra_config)

        self.keyword = self.KEYWORD

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.command_text = event_parser.command(self.keyword).strip()

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.json_report: dict[str, Any] = {}

    @override
    async def should_execute(self) -> bool:
        candidates = self.command_text.split()
        for candidate in candidates:
            if candidate == USER_ALL or (
                self.server_name and candidate in self.server_name
            ):
                return True
        return False

    @override
    async def simple_execute(self) -> bool:
        self.json_report["command"] = self.KEYWORD
        self.json_report["description"] = f"I am {self.server_name}"
        await self.send_report()
        return True

    async def send_report(self) -> None:
        await send_report(
            json_report=self.json_report,
            report_name=self.keyword,
            matrix_client=self.matrix_client,
            room_id=self.room.room_id,
            replied_event_id=self.message.event_id,
        )

    @property
    @override
    def confirm_message(self) -> str | None:
        return "You are about to ping all bots"

    @property
    def help_message(self) -> str:
        return """
**Usage**:
`!ping  ...`

**Purpose**:
Ping bot

**Effects**:
- Return a message by each bot

**Examples**:
- `!ping`
"""
