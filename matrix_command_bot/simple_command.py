from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import CommandAction, CommandWithSteps, ICommandStep
from matrix_command_bot.step.reaction_steps import (
    ReactionCommandState,
    ReactionStep,
    ResultReactionStep,
)


class SimpleExecuteStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        state: ReactionCommandState,
        fct: Callable[[], Awaitable[bool]],
    ) -> None:
        super().__init__(command)
        self.fct = fct
        self.state = state

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        return await self.fct(), CommandAction.CONTINUE


class SimpleCommand(CommandWithSteps, ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.state = ReactionCommandState()

    @override
    async def create_steps(self) -> list[ICommandStep]:
        if not await self.should_execute():
            return []

        return [
            ReactionStep(self, self.state, "🚀"),
            SimpleExecuteStep(self, self.state, self.simple_execute),
            ResultReactionStep(self, self.state),
        ]

    async def should_execute(self) -> bool:
        return True

    @abstractmethod
    async def simple_execute(self) -> bool: ...
