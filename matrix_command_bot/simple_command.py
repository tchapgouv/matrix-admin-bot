from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from nio import RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import CommandAction, CommandWithSteps, ICommandStep
from matrix_command_bot.step.simple_steps import ReactionStep, ResultReactionStep


class SimpleExecuteStep(ICommandStep):
    def __init__(self, command: ICommand, fct: Callable[[], Awaitable[bool]]) -> None:
        super().__init__(command)
        self.fct = fct

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        return await self.fct(), CommandAction.CONTINUE


class SimpleCommand(CommandWithSteps, ABC):
    @override
    async def create_steps(self) -> list[ICommandStep]:
        if not await self.should_execute():
            return []

        return [
            ReactionStep(self, "🚀"),
            SimpleExecuteStep(self, self.simple_execute),
            ResultReactionStep(self),
        ]

    async def should_execute(self) -> bool:
        return True

    @abstractmethod
    async def simple_execute(self) -> bool: ...
