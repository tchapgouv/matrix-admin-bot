from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import structlog
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_server_name, is_local_user, send_report
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand

logger = structlog.getLogger(__name__)


class SingleUserValidatedCommand(SimpleValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        secure_validator: IValidator,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, secure_validator, extra_config)

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        if reply.sender == self.message.sender:
            await self.resume_execute(reply)


class UserRelatedCommand(SingleUserValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        keyword: str,
        extra_config: Mapping[str, Any],
    ) -> None:
        secure_validator: IValidator = extra_config.get("secure_validator")  # pyright: ignore[reportAssignmentType]

        super().__init__(room, message, matrix_client, secure_validator, extra_config)

        self.keyword = keyword

        self.transform_cmd_input_fct: (
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
        ) = extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.input_text = event_parser.command(keyword)

        # Check if this is a help request
        if self.input_text.strip() == "help":
            self.is_help_request = True
        else:
            self.is_help_request = False
            self.user_ids = self.input_text.split()

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.json_report: dict[str, Any] = {}

    @override
    async def should_execute(self) -> bool:
        if self.is_help_request:
            await self.send_help()
            return False

        if self.transform_cmd_input_fct:
            self.user_ids = await self.transform_cmd_input_fct(
                self.__class__, self.user_ids
            )
        return any(
            is_local_user(user_id, self.server_name) for user_id in self.user_ids
        )

    async def send_help(self) -> None:
        """Send the command's help message."""
        if self.help_message:
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                self.help_message,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

    async def send_report(self) -> None:
        await send_report(
            json_report=self.json_report,
            report_name=self.keyword,
            matrix_client=self.matrix_client,
            room_id=self.room.room_id,
            replied_event_id=self.message.event_id,
        )

    @property
    def help_message(self) -> str | None:
        """Return the help message for this command.

        This should be overridden by subclasses to provide specific help text.
        """
        return f"""
## {self.keyword} Command Help

**Usage**: `!{self.keyword} <user1> [user2] ...`
"""
