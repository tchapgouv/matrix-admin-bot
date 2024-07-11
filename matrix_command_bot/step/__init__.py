from abc import abstractmethod
from collections.abc import Mapping
from enum import Enum
from typing import Any

from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand


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

    async def execute(
        self,
        reply: RoomMessage | None = None,  # noqa: ARG002
    ) -> tuple[bool, CommandAction]:
        return True, CommandAction.CONTINUE

    @property
    def status_reaction(self) -> str | None:
        return None


class CommandWithSteps(ICommand):
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

    @abstractmethod
    async def create_steps(self) -> list[ICommandStep]: ...

    @override
    async def execute(self) -> bool:
        self.steps = await self.create_steps()
        return await self.resume_execute(None)

    async def resume_execute(self, reply: RoomMessage | None) -> bool:
        while self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]

            # TODO handle exception ?
            res, action = await self.execute_step(step, reply)

            if not res:
                self.current_result = False
            if action == CommandAction.ABORT:
                return self.current_result
            if action == CommandAction.WAIT_FOR_NEXT_REPLY:
                return True
            if action == CommandAction.RETRY:
                continue

            reply = None
            self.current_step_index += 1

        return self.current_result

    async def execute_step(
        self, step: ICommandStep, reply: RoomMessage | None
    ) -> tuple[bool, CommandAction]:
        await self.set_status_reaction(step.status_reaction)
        return await step.execute(reply)

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        await self.resume_execute(reply)
