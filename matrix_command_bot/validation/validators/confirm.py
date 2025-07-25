from typing import Final

from nio import RoomMessage, RoomMessageText
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_fallback_stripped_body
from matrix_command_bot.validation import IValidator


class ConfirmValidator(IValidator):
    CONFIRM_KEYWORDS: Final = [
        "yes",
        "ok",
        "confirm",
    ]

    def __init__(self) -> None:
        pass

    @property
    @override
    def prompt(self) -> str | None:
        return (
            "Please reply to this message with `yes`, `ok` or `confirm`"
            " to validate and execute the command."
        )

    @property
    @override
    def reaction(self) -> str | None:
        return "✏️"

    @override
    async def validate(
        self,
        user_response: RoomMessage | None,
        command: ICommand,
    ) -> bool:
        if isinstance(user_response, RoomMessageText):
            body = get_fallback_stripped_body(user_response)
            return body.strip().strip(".") in self.CONFIRM_KEYWORDS
        return False
