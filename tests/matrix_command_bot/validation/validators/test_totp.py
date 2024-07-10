import pyotp
import pytest
from matrix_bot.client import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.validation.simple_command import SimpleValidatedCommand
from matrix_command_bot.validation.validators.totp import TOTPValidator
from tests import USER1_ID, create_fake_command_bot, create_thread_relation

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
    mocked_client, t = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )

    mocked_client.check_sent_reactions("🔢")
    mocked_client.check_sent_message("authentication code")

    code = pyotp.TOTP(TOTP_SEED).now()
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, code, content=create_thread_relation(command_event_id)
    )

    assert mocked_client.executed

    t.cancel()


@pytest.mark.asyncio()
async def test_failures_then_success() -> None:
    mocked_client, t = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid1:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )

    mocked_client.send_text_message.reset_mock()

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "yes", content=create_thread_relation(command_event_id)
    )

    mocked_client.check_sent_message("parse")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "000000", content=create_thread_relation(command_event_id)
    )

    mocked_client.check_sent_message("Wrong authentication code")

    assert not mocked_client.executed

    t.cancel()
