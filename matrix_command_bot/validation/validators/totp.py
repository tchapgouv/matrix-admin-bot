from nio import RoomMessage, RoomMessageText
from pyotp import TOTP
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_fallback_stripped_body
from matrix_command_bot.validation import IValidator


class TOTPValidator(IValidator):
    def __init__(self, totps: dict[str, str]) -> None:
        super().__init__()
        self.totps = {user_id: TOTP(totp_seed) for user_id, totp_seed in totps.items()}

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
            body = get_fallback_stripped_body(user_response)
            totp_code = body.replace(" ", "")

            if len(totp_code) == 6 and totp_code.isdigit():
                totp_checker = self.totps.get(command.message.sender)
                if not totp_checker:
                    error_msg = "You are not allowed to execute secure commands, sorry."
                elif not totp_checker.verify(totp_code):
                    error_msg = "Wrong authentication code."
            else:
                error_msg = (
                    "Couldnt parse the authentication code, "
                    "it should be a 6 digits code."
                )
            if error_msg is not None:
                await command.matrix_client.send_text_message(
                    command.room.room_id,
                    error_msg,
                    reply_to=user_response.event_id,
                    thread_root=command.message.event_id,
                )
                return False

            return True

        return False
