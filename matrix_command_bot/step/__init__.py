from abc import abstractmethod

from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand


class ICommandStep:
    def __init__(
        self,
        command: ICommand,
    ) -> None:
        self.command = command

    async def execute(self, reply: RoomMessage | None = None) -> bool:  # noqa: ARG002
        return True

    @property
    def status_reaction(self) -> str | None:
        return None

    def wait_for_next_reply(self, current_reply: RoomMessage | None) -> bool:  # noqa: ARG002
        return False


class CommandWithSteps(ICommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ) -> None:
        super().__init__(room, message, matrix_client)
        self.current_step: ICommandStep | None = None
        self.current_result = True

    @abstractmethod
    async def create_steps(self) -> list[ICommandStep]: ...

    @override
    async def execute(self) -> bool:
        self.steps = await self.create_steps()
        return await self.resume_execute(None)

    async def resume_execute(self, reply: RoomMessage | None) -> bool:
        i = 0
        if self.current_step:
            i = self.steps.index(self.current_step)
        for step in self.steps[i:]:
            self.current_step = step
            if step.wait_for_next_reply(reply):
                return True

            res = await self.execute_step(step, reply)
            reply = None
            if not res:
                self.current_result = False

        return self.current_result

    async def execute_step(self, step: ICommandStep, reply: RoomMessage | None) -> bool:
        await self.set_status_reaction(step.status_reaction)
        return await step.execute(reply)

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        await self.resume_execute(reply)
