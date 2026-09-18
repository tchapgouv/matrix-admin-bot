import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    USER,
    assert_non_local_user_rejected,
    mock_requests,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_lock() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!lock @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_file_message()

    # one call to fetch the devices
    check_requests_sent(mocked_matrix_client.send, "/devices")
    # 1 call to get the mas user id on MAS
    # 1 call to lock user
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/lock",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_lock() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        (
            "GET",
            "/api/admin/v1/users/by-username",
            mock_response_error(404, "Not found"),
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!lock @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message("Couldn't lock")

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_lock() -> None:
    await assert_non_local_user_rejected("!lock @user_to_reset:example2.org")
