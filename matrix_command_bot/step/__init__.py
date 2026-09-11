from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from typing import Any, override

import structlog
from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_command_bot.command import ICommand


class CommandAction(Enum):
    ABORT = 1
    CONTINUE = 2
    RETRY = 3
    WAIT_FOR_NEXT_REPLY = 4


logger = structlog.getLogger(__name__)


class ICommandStep:
    def __init__(
        self,
        command: ICommand,
    ) -> None:
        self.command = command

    async def execute(
        self,
        reply: RoomMessage | None = None,  # noqa: ARG002
    ) -> tuple[bool, CommandAction]:
        logger.debug(
            "Executing default no-op step",
            step=self.__class__.__name__,
            command=self.command,
        )
        return True, CommandAction.CONTINUE


class CommandWithSteps(ICommand, ABC):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.current_step_index: int = 0
        self.current_result = True
        self.is_step_running = False

    @abstractmethod
    async def create_steps(self) -> list[ICommandStep]: ...

    @override
    async def execute(self) -> bool:
        self.steps = await self.create_steps()
        logger.debug(
            "Executing command steps",
            command=self,
            nb_steps=len(self.steps),
        )
        return await self.resume_execute(None)

    async def resume_execute(self, reply: RoomMessage | None) -> bool:
        while self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            logger.debug(
                "Resuming command execution",
                command=self,
                step=step.__class__.__name__,
                step_index=self.current_step_index,
                has_reply=reply is not None,
            )

            # TODO handle exception ?
            res, action = await self.execute_step(step, reply)
            logger.debug(
                "Step executed",
                command=self,
                step=step.__class__.__name__,
                step_index=self.current_step_index,
                result=res,
                action=action.name,
            )

            if not res:
                self.current_result = False
            if action == CommandAction.ABORT:
                logger.debug("Command execution aborted", command=self)
                return self.current_result
            if action == CommandAction.WAIT_FOR_NEXT_REPLY:
                logger.debug("Command is waiting for the next reply", command=self)
                return True
            if action == CommandAction.RETRY:
                logger.debug(
                    "Retrying current step",
                    command=self,
                    step=step.__class__.__name__,
                )
                continue

            reply = None
            self.current_step_index += 1

        logger.debug(
            "Command execution finished",
            command=self,
            result=self.current_result,
        )
        return self.current_result

    async def execute_step(
        self, step: ICommandStep, reply: RoomMessage | None
    ) -> tuple[bool, CommandAction]:
        self.is_step_running = True
        result = await step.execute(reply)
        self.is_step_running = False
        return result

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        if self.is_step_running:
            logger.warning(
                "Step %s is already running",
                self.steps[self.current_step_index].__class__.__name__,
            )
        else:
            logger.debug(
                "Resuming command execution with reply",
                command=self,
                reply=reply,
                step_index=self.current_step_index,
            )
            await self.resume_execute(reply)
