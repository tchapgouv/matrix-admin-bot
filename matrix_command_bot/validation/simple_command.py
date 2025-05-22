from abc import ABC
from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.simple_command import (
    SimpleCommand,
    SimpleExecuteStep,
)
from matrix_command_bot.step import ICommandStep
from matrix_command_bot.step.reaction_steps import (
    ReactionCommandState,
    ReactionStep,
    ResultReactionStep,
)
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.steps import ValidateStep

logger = structlog.getLogger(__name__)


class SimpleValidatedCommand(SimpleCommand, ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        validator: IValidator,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing SimpleValidatedCommand",
            room_id=room.room_id,
            event_id=message.event_id,
            validator=type(validator).__name__,
        )
        super().__init__(room, message, matrix_client, extra_config)
        self.validator = validator
        self.state = ReactionCommandState()

    @override
    async def create_steps(self) -> list[ICommandStep]:
        logger.debug(
            "SimpleValidatedCommand.create_steps called", command=type(self).__name__
        )
        command = self

        if not await self.should_execute():
            logger.debug(
                "SimpleValidatedCommand.should_execute returned False",
                command=type(self).__name__,
            )
            return [
                ValidateStep(self, self.state, self.validator, command.confirm_message),
                ReactionStep(self, self.state, ""),
            ]

        logger.debug(
            "SimpleValidatedCommand.should_execute returned True",
            command=type(self).__name__,
        )
        return [
            ValidateStep(self, self.state, self.validator, command.confirm_message),
            ReactionStep(self, self.state, "🚀"),
            SimpleExecuteStep(self, self.state, self.simple_execute),
            ResultReactionStep(self, self.state),
        ]

    @property
    def confirm_message(self) -> str | None:
        logger.debug(
            "SimpleValidatedCommand.confirm_message called", command=type(self).__name__
        )
        return None

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        logger.debug(
            "SimpleValidatedCommand.reply_received called",
            reply_id=getattr(reply, "event_id", None),
        )
        # do not allow other users to interact with the command
        if reply.sender == self.message.sender:
            await super().reply_received(reply)
