from typing import Final

import structlog
from nio import RoomMessage, RoomMessageText
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_fallback_stripped_body
from matrix_command_bot.validation import IValidator

logger = structlog.getLogger(__name__)


class ConfirmValidator(IValidator):
    CONFIRM_KEYWORDS: Final = [
        "yes",
        "ok",
        "confirm",
    ]

    def __init__(self) -> None:
        logger.debug("Initialized ConfirmValidator")

    @property
    @override
    def prompt(self) -> str | None:
        logger.debug("ConfirmValidator.prompt called")
        return (
            "Please reply to this message with `yes`, `ok` or `confirm`"
            " to validate and execute the command."
        )

    @property
    @override
    def reaction(self) -> str | None:
        logger.debug("ConfirmValidator.reaction called")
        return "✏️"

    @override
    async def validate(
        self,
        user_response: RoomMessage | None,
        command: ICommand,
    ) -> bool:
        logger.debug(
            "ConfirmValidator.validate called",
            user_response_id=getattr(user_response, "event_id", None),
        )
        if isinstance(user_response, RoomMessageText):
            body = get_fallback_stripped_body(user_response)
            result = body.strip().strip(".") in self.CONFIRM_KEYWORDS
            logger.debug(
                "ConfirmValidator: Validation result",
                result=result,
                user=command.message.sender,
            )
            return result
        logger.debug("ConfirmValidator: No valid response", user=command.message.sender)
        return False
