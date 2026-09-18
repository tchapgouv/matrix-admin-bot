import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
    find_request,
)
from tests.matrix_admin_bot.commands.next import (
    USER,
    USER_EMAIL,
    USER_EMAILS_LIST,
    assert_non_local_user_rejected,
    mock_requests,
    mock_response_error,
    mock_response_with_json,
    mock_send_routes,
)


@pytest.mark.asyncio
async def test_replace_email() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_routes(
        (
            "GET",
            "/_matrix/identity/api/v1/info?medium=email&address=newemail@domain.tld",
            mock_response_with_json({"hs": "example.org"}),
        ),
        default=mock_response_with_json({}),
    )
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        ("GET", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAILS_LIST)),
        ("POST", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAIL)),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!replace_email @user_to_reset:example.org newemail@domain.tld"
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to get the mas user id on MAS
    # 1 call to get all emails
    # 1 call to delete old email
    # 1 call to add email
    add_email_request = find_request(
        mocked_matrix_client.client_session, "POST", "/user-emails"
    )
    assert add_email_request.kwargs["json"]["email"] == "newemail@domain.tld"
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/user-emails",
        "/user-emails",
        "/user-emails",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_replace_email_with_new_email_on_wrong_homeserver() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_routes(
        (
            "GET",
            "/_matrix/identity/api/v1/info?medium=email&address=newemail@domain.tld",
            mock_response_with_json({"hs": "other.example.org"}),
        ),
        default=mock_response_with_json({}),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!replace_email @user_to_reset:example.org newemail@domain.tld"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't replace email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_replace_email_when_api_in_error() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_routes(
        (
            "GET",
            "/_matrix/identity/api/v1/info?medium=email&address=user@domain.tld",
            mock_response_with_json({"hs": "example.org"}),
        ),
        default=mock_response_with_json({}),
    )
    mocked_matrix_client.client_session.request.return_value = mock_response_error(
        403, "Forbidden"
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!replace_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't replace email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_replace_email() -> None:
    await assert_non_local_user_rejected(
        "!replace_email @user_to_reset:example2.org user@domain.tld"
    )
