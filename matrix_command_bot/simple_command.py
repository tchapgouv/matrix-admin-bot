from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import structlog
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
        logger.debug("Initialized SimpleExecuteStep", command=type(command).__name__)

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        logger.debug("Executing SimpleExecuteStep", command=type(self.command).__name__)
        return await self.fct(), CommandAction.CONTINUE


class SimpleCommand(CommandWithSteps, ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing SimpleCommand",
            room_id=room.room_id,
            event_id=message.event_id,
        )
        super().__init__(room, message, matrix_client, extra_config)
        self.state = ReactionCommandState()

    @override
    async def create_steps(self) -> list[ICommandStep]:
        logger.debug("SimpleCommand.create_steps called", command=type(self).__name__)
        if not await self.should_execute():
            logger.debug(
                "SimpleCommand.should_execute returned False",
                command=type(self).__name__,
            )
            return []
        logger.debug(
            "SimpleCommand.should_execute returned True", command=type(self).__name__
        )
        return [
            ReactionStep(self, self.state, "🚀"),
            SimpleExecuteStep(self, self.state, self.simple_execute),
            ResultReactionStep(self, self.state),
        ]

    async def should_execute(self) -> bool:
        logger.debug("SimpleCommand.should_execute called", command=type(self).__name__)
        return True

    @abstractmethod
    async def simple_execute(self) -> bool: ...
