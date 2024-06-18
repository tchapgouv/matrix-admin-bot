from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

import matrix_command_bot
from matrix_admin_bot.commands.reset_password import ResetPasswordCommand
from matrix_command_bot.commandbot import CommandBot
from tests import USER1_ID, OkValidator, mock_client_and_run


@pytest.mark.asyncio()
async def test_reset_password() -> None:
    matrix_command_bot.validation.SECURE_VALIDATOR = OkValidator()
    bot = CommandBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=[ResetPasswordCommand],
        coordinator=None,
    )
    mocked_client, t = await mock_client_and_run(bot)
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password @user_to_reset:example.org"
    )

    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()

    # one call to fetch the devices, and one call to reset the password
    assert len(mocked_client.send.await_args_list) == 2
    assert "/devices" in mocked_client.send.await_args_list[0][0][1]
    assert "/reset_password/" in mocked_client.send.await_args_list[1][0][1]
    mocked_client.send.reset_mock()

    t.cancel()
