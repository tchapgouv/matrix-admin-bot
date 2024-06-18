from abc import abstractmethod
from enum import Enum

from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage

DEFAULT_MESSAGE = "Please reply to go the next stage"


class CommandStepStatus(Enum):
    READY = 1
    IN_PROGRESS = 2
    SUCCESS = 3
    FAILED = 3


class CommandStep:
    def __init__(self, message: str = DEFAULT_MESSAGE) -> None:
        self.message_store: set[str] = set()
        self.state: CommandStepStatus = CommandStepStatus.READY
        self.message = message

    async def process(self,
                      room: MatrixRoom,
                      message: RoomMessage,
                      matrix_client: MatrixClient,
                      thread_root_message: RoomMessage) -> None:
        self.message_store.add(message.event_id)

        if self.state in [CommandStepStatus.READY]:
            await self.send_validation_message(message, thread_root_message, room, matrix_client)
        elif self.state == CommandStepStatus.IN_PROGRESS:
            if await self.validate(message, thread_root_message, room, matrix_client):
                self.state = CommandStepStatus.SUCCESS
            else:
                await self.send_validation_message(message, thread_root_message, room, matrix_client)

    async def send_validation_message(self, message: RoomMessage, thread_root_message: RoomMessage,
                                      room: MatrixRoom, matrix_client: MatrixClient):
        validation_message = self.validation_message()
        await matrix_client.send_markdown_message(
            room.room_id,
            validation_message,
            reply_to=message.event_id,
            thread_root=thread_root_message.event_id,
        )
        self.state = CommandStepStatus.IN_PROGRESS

    def get_related_event_id(self, message: RoomMessage):
        return message.source.get("content", {}).get("m.relates_to", {}).get("event_id")

    def match(self, message: RoomMessage) -> bool:
        return len(self.message_store) == 0 or self.get_related_event_id(message) in self.message_store

    def is_success(self) -> bool:
        return self.state == CommandStepStatus.SUCCESS

    def validation_message(self) -> str:
        return self.message

    @abstractmethod
    async def validate(self,
                       user_response: RoomMessage,
                       thread_root_message: RoomMessage,
                       room: MatrixRoom,
                       matrix_client: MatrixClient) -> bool:
        ...
