from abc import ABC, abstractmethod
from functools import reduce

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.command_validator import CommandValidatorStep


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


class CommandToValidate(Command):

    def __init__(
            self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
            totps: dict[str, str] | None,
    ) -> None:
        super().__init__(room, message, matrix_client)
        self.totps = totps
        self.command_validator: list[CommandValidatorStep] = []

    # # TODO: remove this or re-use this
    # @staticmethod
    # @abstractmethod
    # def needs_secure_validation() -> bool:
        ...

    async def process_validator_steps(self, message: RoomMessage):
        # the validation should come from the sender of the command
        if self.message.sender != message.sender:
            return
        command_validator = self.get_next_command_validator()
        if command_validator:
            await command_validator.process(self.room, message, self.matrix_client, self.message)
            if command_validator.is_success():
                next_command_validator = self.get_next_command_validator()
                if next_command_validator:
                    await next_command_validator.process(self.room, message, self.matrix_client, self.message)

    def get_next_command_validator(self):
        for command_validator in self.command_validator:
            if not command_validator.is_success():
                return command_validator
        return None

    def is_valid(self):
        return reduce(lambda x, y: x and y.is_success(), self.command_validator, True)
