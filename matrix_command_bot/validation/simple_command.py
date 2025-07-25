from abc import ABC
from collections.abc import Mapping
from typing import Any

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


class SimpleValidatedCommand(SimpleCommand, ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        validator: IValidator,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.validator = validator
        self.state = ReactionCommandState()

    @override
    async def create_steps(self) -> list[ICommandStep]:
        command = self

        if not await self.should_execute():
            return [
                ValidateStep(self, self.state, self.validator, command.confirm_message),
                ReactionStep(self, self.state, ""),
            ]

        return [
            ValidateStep(self, self.state, self.validator, command.confirm_message),
            ReactionStep(self, self.state, "🚀"),
            SimpleExecuteStep(self, self.state, self.simple_execute),
            ResultReactionStep(self, self.state),
        ]

    @property
    def confirm_message(self) -> str | None:
        return None

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        await super().reply_received(reply)
