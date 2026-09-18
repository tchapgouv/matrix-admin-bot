from unittest.mock import AsyncMock

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
    USER_EMAIL,
    USER_EMAILS_LIST,
    assert_non_local_user_rejected,
    mock_requests,
    mock_response_error,
    mock_response_with_json,
    mock_send_routes,
    with_params,
)

IDENTITY_EMAIL_ENDPOINT = (
    "/_matrix/identity/api/v1/info?medium=email&address=user@domain.tld"
)


def mock_identity_routes() -> AsyncMock:
    return mock_send_routes(
        (
            "GET",
            IDENTITY_EMAIL_ENDPOINT,
            mock_response_with_json({"hs": "example.org"}),
        ),
        default=mock_response_with_json({}),
    )


@pytest.mark.asyncio
async def test_add_email() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_identity_routes()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        ("GET", "/api/admin/v1/user-emails", mock_response_error(404, "Not Found")),
        ("POST", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAIL)),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to get the mas user id on MAS
    # 1 call to check if email is not used
    # 1 call to check if user has no email
    # 1 call to add email
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/user-emails",
        "/user-emails",
        "/user-emails",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_add_email_when_email_already_used() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_identity_routes()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        (
            "GET",
            with_params("/api/admin/v1/user-emails", "filter[email]"),
            mock_response_with_json(USER_EMAILS_LIST),
        ),
        ("POST", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAIL)),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't add email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_add_email_when_user_has_email() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_identity_routes()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        # Our user is already using this email
        (
            "GET",
            with_params("/api/admin/v1/user-emails", "filter[user]"),
            mock_response_with_json(USER_EMAILS_LIST),
        ),
        ("GET", "/api/admin/v1/user-emails", mock_response_error(404, "Not found")),
        ("POST", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAIL)),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't add email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_add_email_when_api_in_error() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_identity_routes()
    mocked_matrix_client.client_session.request.return_value = mock_response_error(
        403, "Forbidden"
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't add email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_add_email() -> None:
    await assert_non_local_user_rejected(
        "!add_email @user_to_reset:example2.org user@domain.tld"
    )
