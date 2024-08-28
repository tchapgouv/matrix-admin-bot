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

    #  one call to set the account validity
    assert len(mocked_client.send.await_args_list) == 1
    assert "/account_validity/" in mocked_client.send.await_args_list[0][0][1]
    mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio()
async def test_failed_account_validity() -> None:
    mocked_client, t = await create_fake_command_bot(
        [AccountValidityCommand], secure_validator=OkValidator()
    )
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=False, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!account_validity @user_to_reset:example.org"
    )

    mocked_client.check_sent_message("Couldn't set the account validity")

    t.cancel()
