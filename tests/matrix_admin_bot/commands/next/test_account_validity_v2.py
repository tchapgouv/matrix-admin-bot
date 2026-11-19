from unittest import mock
from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from tests.helper import USER1_ID, OkValidator, create_fake_admin_bot


@pytest.mark.asyncio
async def test_account_validity() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!account_validity @user_to_reset:example.org"
    )

    # send the report a result
    mocked_matrix_client.check_sent_report()

    #  one call to set the account validity
    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert (
        "/email_account_validity/admin"
        in mocked_matrix_client.send.await_args_list[0][0][1]
    )

    assert len(mocked_matrix_client.send_reaction.await_args_list) == 2
    mocked_matrix_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_account_validity_with_error_500() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=False, json=AsyncMock(return_value={}), status=500)
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    with mock.patch("asyncio.sleep", new_callable=AsyncMock):
        await mocked_matrix_client.fake_synced_text_message(
            room, USER1_ID, "!account_validity @user_to_reset:example.org"
        )

    # send the report a result
    mocked_matrix_client.check_sent_report()

    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_matrix_client.send.await_args_list) == 3
    assert (
        "/email_account_validity/admin"
        in mocked_matrix_client.send.await_args_list[0][0][1]
    )
    mocked_matrix_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_account_validity_on_other_instance() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!account_validity @user_to_reset:anotherexample.org"
    )

    # send the report a result
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send_file_message.assert_not_awaited()
    mocked_matrix_client.send_html_message.reset_mock()
    mocked_matrix_client.send_html_message.assert_not_awaited()

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
