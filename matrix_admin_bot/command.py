from abc import ABC, abstractmethod
from functools import reduce

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.command_step import CommandStep


class Command(ABC):
    def __init__(
            self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
    ) -> None:
        self.room = room
        self.message = message
        self.matrix_client = matrix_client
        self.current_status_reaction = None

    async def set_status_reaction(self, key: str | None) -> None:
        if self.current_status_reaction:
            await self.matrix_client.room_redact(
                self.room.room_id, self.current_status_reaction
            )
        if key:
            self.current_status_reaction = await self.matrix_client.send_reaction(
                self.room.room_id, self.message, key
            )

    async def send_result(self) -> None:
        return

    @abstractmethod
    async def execute(self) -> bool:
        ...


class CommandWithSteps(Command):

    def __init__(
            self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
            totps: dict[str, str] | None,
    ) -> None:
        super().__init__(room, message, matrix_client)
        self.totps = totps
        self.command_steps: list[CommandStep] = []

    # # TODO: remove this or re-use this
    # @staticmethod
    # @abstractmethod
    # def needs_secure_validation() -> bool:
        ...

    async def process_steps(self, message: RoomMessage):
        # the validation should come from the sender of the command
        if self.message.sender != message.sender:
            return
        command_steps = self.get_next_command_step()
        if command_steps:
            await command_steps.process(self.room, message, self.matrix_client, self.message)
            if command_steps.is_success():
                next_command_step = self.get_next_command_step()
                if next_command_step:
                    await next_command_step.process(self.room, message, self.matrix_client, self.message)

    def get_next_command_step(self):
        for command_step in self.command_steps:
            if not command_step.is_success():
                return command_step
        return None

    def is_valid(self):
        return reduce(lambda x, y: x and y.is_success(), self.command_steps, True)
