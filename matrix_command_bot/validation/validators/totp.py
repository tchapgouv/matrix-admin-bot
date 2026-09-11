from typing import override

import structlog
from nio import RoomMessage, RoomMessageText
from pyotp import TOTP

from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_fallback_stripped_body
from matrix_command_bot.validation import IValidator

logger = structlog.getLogger(__name__)


class TOTPValidator(IValidator):
    def __init__(self, totps: dict[str, str]) -> None:
        super().__init__()
        self.totps = {user_id: TOTP(totp_seed) for user_id, totp_seed in totps.items()}
        logger.debug("TOTP validator initialized", nb_totps=len(self.totps))

    @property
    @override
    def prompt(self) -> str | None:
        return (
            "Please reply to this message with an authentication code"
            " to validate and execute the command."
        )

    @property
    @override
    def reaction(self) -> str | None:
        return "🔢"

    @override
    async def validate(
        self,
        user_response: RoomMessage | None,
        command: ICommand,
    ) -> bool:
        error_msg = None

        if isinstance(user_response, RoomMessageText):
            logger.debug(
                "Validating TOTP code",
                command=command,
                sender=user_response.sender,
            )
            body = get_fallback_stripped_body(user_response)
            totp_code = body.replace(" ", "")

            if len(totp_code) == 6 and totp_code.isdigit():
                totp_checker = self.totps.get(user_response.sender)
                if not totp_checker:
                    logger.warning(
                        "TOTP validation failed: user has no TOTP configured",
                        command=command,
                        sender=user_response.sender,
                    )
                    error_msg = "You are not allowed to execute secure commands, sorry."
                elif not totp_checker.verify(totp_code, valid_window=1):
                    logger.warning(
                        "TOTP validation failed: wrong authentication code",
                        command=command,
                        sender=user_response.sender,
                    )
                    error_msg = "Wrong authentication code."
            else:
                logger.debug(
                    "TOTP validation failed: could not parse the authentication code",
                    command=command,
                    sender=user_response.sender,
                )
                error_msg = (
                    "Couldnt parse the authentication code, "
                    "it should be a 6 digits code."
                )
            if error_msg is not None:
                if command.extra_config.get("is_coordinator", True):
                    await command.matrix_client.send_text_message(
                        command.room.room_id,
                        error_msg,
                        reply_to=user_response.event_id,
                        thread_root=command.message.event_id,
                    )
                return False

            logger.debug(
                "TOTP validation succeeded",
                command=command,
                sender=user_response.sender,
            )
            return True

        logger.debug(
            "TOTP validation waiting for a text reply",
            command=command,
        )
        return False
