from typing import Final

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessageText, RoomMessage
from typing_extensions import override

from matrix_admin_bot.command_validator import CommandValidatorStep
from matrix_admin_bot.util import get_fallback_stripped_body


class ConfirmCommandValidatorStep(CommandValidatorStep):
    CONFIRM_KEYWORDS: Final = [
        "yes",
        "ok",
        "confirm",
    ]

    @override
    def validation_message(self) -> str :
        return (
            "Please reply to this message with `yes`, `ok` or `confirm`"
            " to validate and execute the command."
        )

    @override
    async def validate(self, user_response: RoomMessage,
                 thread_root_message: RoomMessage,
                 room: MatrixRoom,
                 matrix_client: MatrixClient) -> bool:
        if not isinstance(user_response, RoomMessageText):
            return False
        body = get_fallback_stripped_body(user_response)
        return body.strip().strip(".") in self.CONFIRM_KEYWORDS


CONFIRM_VALIDATOR_STEP = ConfirmCommandValidatorStep()

