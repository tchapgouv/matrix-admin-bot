from abc import ABC
from collections.abc import Mapping
from typing import Any

from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.simple_command import SimpleCommand, SimpleExecuteStep
from matrix_command_bot.step import ICommandStep
from matrix_command_bot.step.simple_steps import ReactionStep, ResultReactionStep
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

    @override
    async def create_steps(self) -> list[ICommandStep]:
        command = self

        class _ValidateStep(ValidateStep):
            @property
            @override
            def message(self) -> str | None:
                return command.confirm_message

        if not await self.should_execute():
            return [_ValidateStep(self, self.validator), ReactionStep(self, "")]

        return [
            _ValidateStep(self, self.validator),
            ReactionStep(self, "🚀"),
            SimpleExecuteStep(self, self.simple_execute),
            ResultReactionStep(self),
        ]

    @property
    def confirm_message(self) -> str | None:
        return None
