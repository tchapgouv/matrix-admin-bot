from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessageText, RoomMessage
from pyotp import TOTP
from typing_extensions import override

from matrix_admin_bot.command_step import CommandStep
from matrix_admin_bot.util import get_fallback_stripped_body

DEFAULT_MESSAGE = (
    "Please reply to this message with an authentication code" 
    " to validate and execute the command."
)


class TOTPCommandStep(CommandStep):

    def __init__(self, totps: dict[str, str], message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)
        self.totps = {user_id: TOTP(totp_seed) for user_id, totp_seed in totps.items()}

    @override
    async def validate(self, user_response: RoomMessage, thread_root_message: RoomMessage, room: MatrixRoom,
                       matrix_client: MatrixClient) -> bool:
        if not isinstance(user_response, RoomMessageText):
            return
        error_msg = None

        body = get_fallback_stripped_body(user_response)
        totp_code = body.replace(" ", "")

        if len(totp_code) == 6 and totp_code.isdigit():
            totp_checker = self.totps.get(thread_root_message.sender)
            if not totp_checker:
                error_msg = "You are not allowed to execute secure commands, sorry."
            elif not totp_checker.verify(totp_code):
                error_msg = "Wrong authentication code."
        else:
            error_msg = (
                "Couldnt parse the authentication code, it should be a 6 digits code."
            )
        if error_msg is not None:
            await matrix_client.send_text_message(
                room.room_id,
                error_msg,
                reply_to=user_response.event_id,
                thread_root=thread_root_message.event_id,
            )
            return False

        return True
