import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    COMPAT_SESSIONS_LIST,
    OAUTH2_SESSIONS_LIST,
    PERSONAL_SESSIONS_LIST,
    UPSTREAM_OAUTH_LINKS_LIST,
    USER,
    USER_EMAILS_LIST,
    USER_SESSIONS_LIST,
    USER_SYNAPSE,
    assert_non_local_user_rejected,
    mock_requests,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
    mock_send_routes,
)


@pytest.mark.asyncio
async def test_user_v2() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_routes(
        ("GET", "/devices", mock_response_with_json({})),
        (
            "GET",
            "/_synapse/admin/v2/users/@user_to_reset:example.org",
            mock_response_with_json(USER_SYNAPSE),
        ),
    )
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        (
            "GET",
            "/api/admin/v1/upstream-oauth-links",
            mock_response_with_json(UPSTREAM_OAUTH_LINKS_LIST),
        ),
        ("GET", "/api/admin/v1/user-emails", mock_response_with_json(USER_EMAILS_LIST)),
        (
            "GET",
            "/api/admin/v1/compat-sessions",
            mock_response_with_json(COMPAT_SESSIONS_LIST),
        ),
        (
            "GET",
            "/api/admin/v1/oauth2-sessions",
            mock_response_with_json(OAUTH2_SESSIONS_LIST),
        ),
        (
            "GET",
            "/api/admin/v1/user-sessions",
            mock_response_with_json(USER_SESSIONS_LIST),
        ),
        (
            "GET",
            "/api/admin/v1/personal-sessions",
            mock_response_with_json(PERSONAL_SESSIONS_LIST),
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!user @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to fetch the devices on synapse
    # 1 call to get user data
    check_requests_sent(
        mocked_matrix_client.send,
        "/devices",
        "/_synapse/admin/v2/users/@user_to_reset:example.org",
    )
    # 1 call to get the mas user id on MAS
    # 1 call to get upstream OAuth links
    # 1 call to get user emails
    # 3 calls to get each session type
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/upstream-oauth-links",
        "/user-emails",
        "/compat-sessions",
        "/oauth2-sessions",
        "/user-sessions",
        "/personal-sessions",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_user_v2() -> None:
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
        room, USER1_ID, "!user @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't get full information of the following users"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_user_v2() -> None:
    await assert_non_local_user_rejected("!user @user_to_reset:example2.org")
