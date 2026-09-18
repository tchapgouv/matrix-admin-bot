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
    USER_EMAILS_LIST,
    USER_EMAILS_LIST_NO_DATA,
    assert_non_local_user_rejected,
    mock_requests,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_remove_email() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        ("GET", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAILS_LIST)),
        (
            "DELETE",
            "/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09",
            mock_response_with_json({}),
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to get the mas user id on MAS
    # 1 call to find if user has an email
    # 1 call to remove_email user
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/user-emails",
        "/user-emails",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_email_when_user_has_no_email() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        # Our user has no email
        (
            "GET",
            "/api/admin/v1/user-emails",
            mock_response_with_json(USER_EMAILS_LIST_NO_DATA),
        ),
        (
            "DELETE",
            "/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09",
            mock_response_with_json({}),
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_email_when_api_in_error() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_remove_email() -> None:
    await assert_non_local_user_rejected("!remove_email @user_to_reset:example2.org")
