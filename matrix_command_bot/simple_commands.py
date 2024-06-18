from abc import abstractmethod
from collections.abc import Awaitable, Callable

from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import CommandWithSteps, ICommandStep
from matrix_command_bot.step.steps import ReactionStep, ResultReactionStep
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.steps import ConfirmStep, ValidateStep


class SimpleExecuteStep(ICommandStep):
    def __init__(self, command: ICommand, fct: Callable[[], Awaitable[bool]]) -> None:
        super().__init__(command)
        self.fct = fct

    @override
    async def execute(self, reply: RoomMessage | None = None)  -> tuple[bool, bool]:
        return await self.fct(), True


class SimpleCommand(CommandWithSteps):
    @override
    async def create_steps(self) -> list[ICommandStep]:
        return [
            ReactionStep(self, "🚀"),
            SimpleExecuteStep(self, self.simple_execute),
            ResultReactionStep(self),
        ]

    @abstractmethod
    async def simple_execute(self) -> bool: ...


class SimpleValidatedCommand(SimpleCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        validator: IValidator,
    ) -> None:
        super().__init__(room, message, matrix_client)
        self.validator = validator

    @override
    async def create_steps(self) -> list[ICommandStep]:
        command = self

        class _ConfirmStep(ConfirmStep):
            @property
            @override
            def message(self) -> str | None:
                return command.confirm_message

        return [
            _ConfirmStep(self, self.validator),
            ValidateStep(self, self.validator),
            ReactionStep(self, "🚀"),
            SimpleExecuteStep(self, self.simple_execute),
            ResultReactionStep(self),
        ]

    @property
    def confirm_message(self) -> str | None:
        return None
