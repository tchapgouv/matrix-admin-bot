from typing import Any

from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot.command import CommandToValidate
from matrix_admin_bot.command_validator import CommandValidatorStep
from matrix_admin_bot.util import get_server_name
# from matrix_admin_bot.validators.confirm import CONFIRM_VALIDATOR_STEP
from matrix_admin_bot.validators.totp import TOTPCommandValidatorStep


# FIXME: remove this when prototype is finised
class TestCommandValidatorStep(CommandValidatorStep):

    @override
    def validation_message(self) -> str:
        return "\n".join(
            [
                "You are about to test a command",
            ]
        )

    @override
    async def validate(self, user_response: RoomMessage,
                 thread_root_message: RoomMessage,
                 room: MatrixRoom,
                 matrix_client: MatrixClient) -> bool:
        return user_response.source.get("content", {}).get("body") == 'ok'


class TestCommandValidatorStep2(CommandValidatorStep):

    @override
    def validation_message(self) -> str :
        return "\n".join(
            [
                "COMMAND NUMBER 2",
            ]
        )

    @override
    async def validate(self, user_response: RoomMessage,
                 thread_root_message: RoomMessage,
                 room: MatrixRoom,
                 matrix_client: MatrixClient) -> bool:
        return user_response.source.get("content", {}).get("body") == 'yes'


class TestCommand(CommandToValidate):
    KEYWORD = "test"

    def __init__(
        self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
            totps: dict[str, str] | None,
    ) -> None:
        super().__init__(room, message, matrix_client, totps)

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        event_parser.command(self.KEYWORD)

        self.failed_user_ids: list[str] = []

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.command_validator: list[CommandValidatorStep] = [TestCommandValidatorStep(),
                                                              TestCommandValidatorStep2(),
                                                              TOTPCommandValidatorStep(totps)]

    @override
    async def execute(self) -> bool:
        print("execute")
        return True

    @override
    async def send_result(self) -> None:
        print("result")


