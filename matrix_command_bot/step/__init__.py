from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from typing import Any

import structlog
from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand

logger = structlog.getLogger(__name__)


class CommandAction(Enum):
    ABORT = 1
    CONTINUE = 2
    RETRY = 3
    WAIT_FOR_NEXT_REPLY = 4


class ICommandStep:
    def __init__(
        self,
        command: ICommand,
    ) -> None:
        self.command = command
        logger.debug("Initialized ICommandStep", command=type(command).__name__)

    async def execute(
        self,
        reply: RoomMessage | None = None,  # noqa: ARG002
    ) -> tuple[bool, CommandAction]:
        logger.debug("ICommandStep.execute called", command=type(self.command).__name__)
        return True, CommandAction.CONTINUE


class CommandWithSteps(ICommand, ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing CommandWithSteps",
            room_id=room.room_id,
            event_id=message.event_id,
        )
        super().__init__(room, message, matrix_client, extra_config)
        self.current_step_index: int = 0
        self.current_result = True

    @abstractmethod
    async def create_steps(self) -> list[ICommandStep]: ...

    @override
    async def execute(self) -> bool:
        logger.debug("CommandWithSteps.execute called", command=type(self).__name__)
        self.steps = await self.create_steps()
        return await self.resume_execute(None)

    async def resume_execute(self, reply: RoomMessage | None) -> bool:
        logger.debug(
            "CommandWithSteps.resume_execute called",
            command=type(self).__name__,
            current_step_index=self.current_step_index,
        )
        while self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            logger.debug(
                "Executing step",
                step=type(step).__name__,
                step_index=self.current_step_index,
            )
            # TODO handle exception ?
            res, action = await self.execute_step(step, reply)

            if not res:
                self.current_result = False
            if action == CommandAction.ABORT:
                logger.debug("Step requested ABORT", step=type(step).__name__)
                return self.current_result
            if action == CommandAction.WAIT_FOR_NEXT_REPLY:
                logger.debug(
                    "Step requested WAIT_FOR_NEXT_REPLY", step=type(step).__name__
                )
                return True
            if action == CommandAction.RETRY:
                logger.debug("Step requested RETRY", step=type(step).__name__)
                continue

            reply = None
            self.current_step_index += 1

        logger.debug("All steps executed", command=type(self).__name__)
        return self.current_result

    async def execute_step(
        self, step: ICommandStep, reply: RoomMessage | None
    ) -> tuple[bool, CommandAction]:
        logger.debug("CommandWithSteps.execute_step called", step=type(step).__name__)
        return await step.execute(reply)

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        logger.debug(
            "CommandWithSteps.reply_received called",
            reply_id=getattr(reply, "event_id", None),
        )
        await self.resume_execute(reply)
