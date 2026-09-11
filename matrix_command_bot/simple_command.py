from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, override

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import CommandAction, CommandWithSteps, ICommandStep
from matrix_command_bot.step.reaction_steps import (
    ReactionCommandState,
    ReactionStep,
    ResultReactionStep,
)

logger = structlog.getLogger(__name__)


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
        logger.debug(
            "Executing simple command step",
            command=self.command,
            has_reply=reply is not None,
        )
        result = await self.fct()
        logger.debug(
            "Simple command step executed",
            command=self.command,
            result=result,
        )
        return result, CommandAction.CONTINUE


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
        should_execute = await self.should_execute()
        logger.debug(
            "Creating steps for simple command",
            command=self,
            should_execute=should_execute,
        )
        if not should_execute:
            logger.debug("Command will not execute, skipping steps", command=self)
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
