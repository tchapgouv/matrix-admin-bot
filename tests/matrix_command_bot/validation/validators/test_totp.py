import pyotp
import pytest
from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.commandbot import CommandBot
from matrix_command_bot.simple_commands import SimpleValidatedCommand
from matrix_command_bot.validation.validators.totp import TOTPValidator
from tests import USER1_ID, mock_client_and_run

TOTP_SEED = "P7ZBD5ZLMACOOTX4"


class ConfirmValidatedCommand(SimpleValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ) -> None:
        super().__init__(
            room, message, matrix_client, TOTPValidator({USER1_ID: TOTP_SEED})
        )

    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return True


@pytest.mark.asyncio()
async def test_success() -> None:
    bot = CommandBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=[ConfirmValidatedCommand],
        coordinator=None,
    )
    mocked_client, t = await mock_client_and_run(bot)
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )

    mocked_client.send_reaction.assert_awaited_once()
    assert mocked_client.send_reaction.await_args
    assert mocked_client.send_reaction.await_args[0][2] == "🔢"
    mocked_client.send_reaction.reset_mock()

    mocked_client.send_markdown_message.assert_awaited_once()
    assert mocked_client.send_markdown_message.await_args
    assert "authentication code" in mocked_client.send_markdown_message.await_args[0][1]
    mocked_client.send_markdown_message.reset_mock()

    thread_relation = {
        "m.relates_to": {
            "event_id": command_event_id,
            "rel_type": "m.thread",
        }
    }
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, pyotp.TOTP(TOTP_SEED).now(), content=thread_relation
    )

    assert mocked_client.executed

    t.cancel()
