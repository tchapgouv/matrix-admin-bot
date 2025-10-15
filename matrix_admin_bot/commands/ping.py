from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.util import get_server_name
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

    @override
    async def simple_execute(self) -> bool:
        text = f"I am {self.server_name}"
        await self.matrix_client.send_markdown_message(
            self.room.room_id,
            text,
            reply_to=self.message.event_id,
            thread_root=self.message.event_id,
        )
        return True

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
