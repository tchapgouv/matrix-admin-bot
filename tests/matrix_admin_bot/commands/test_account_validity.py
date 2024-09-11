from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from matrix_admin_bot.commands.account_validity import AccountValidityCommand
from tests import USER1_ID, OkValidator, create_fake_command_bot


@pytest.mark.asyncio()
async def test_account_validity() -> None:
    mocked_client, t = await create_fake_command_bot(
        [AccountValidityCommand], secure_validator=OkValidator()
    )
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!account_validity @user_to_reset:example.org"
    )

    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    #  one call to set the account validity
    assert len(mocked_client.send.await_args_list) == 1
    assert "/account_validity/" in mocked_client.send.await_args_list[0][0][1]
    mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio()
async def test_failed_account_validity_with_error_500() -> None:
    mocked_client, t = await create_fake_command_bot(
        [AccountValidityCommand], secure_validator=OkValidator()
    )
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=False, json=AsyncMock(return_value={}), status=500)
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!account_validity @user_to_reset:example.org"
    )

    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_client.send.await_args_list) == 10
    assert "/account_validity/validity" in mocked_client.send.await_args_list[0][0][1]
    mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio()
async def test_failed_account_validity_on_other_instance() -> None:
    mocked_client, t = await create_fake_command_bot(
        [AccountValidityCommand], secure_validator=OkValidator()
    )
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!account_validity @user_to_reset:anotherexample.org"
    )

    # send the report a result
    mocked_client.send_file_message.assert_not_awaited()
    mocked_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_client.send.await_args_list) == 0
    mocked_client.send.reset_mock()

    t.cancel()
