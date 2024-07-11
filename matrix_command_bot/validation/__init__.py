from abc import ABC, abstractmethod

from nio import RoomMessage

from matrix_command_bot.command import ICommand


class IValidator(ABC):
    @property
    def prompt(self) -> str | None:
        return None

    @property
    def reaction(self) -> str | None:
        return None

    @abstractmethod
    async def validate(
        self,
        user_response: RoomMessage | None,
        command: ICommand,
    ) -> bool: ...
