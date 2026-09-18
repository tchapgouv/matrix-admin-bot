import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    UPSTREAM_OAUTH_LINKS_EMPTY,  # type: ignore
    UPSTREAM_OAUTH_LINKS_LIST,
    USER,
    assert_non_local_user_rejected,
    mock_requests,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_remove_upstream_oauth_links() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        (
            "GET",
            "/api/admin/v1/upstream-oauth-links",
            mock_response_with_json(UPSTREAM_OAUTH_LINKS_LIST),
        ),
        (
            "DELETE",
            "/upstream-oauth-links/01K5R30ZEENQQCR9ZPQY9KYP0A",
            mock_response_with_json({}),
        ),
        (
            "DELETE",
            "/upstream-oauth-links/01K5R30ZEENQQCR9ZPQY9KYP0B",
            mock_response_with_json({}),
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_upstream_oauth_links @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to get the mas user id on MAS
    # 1 call to find upstream OAuth links
    # 2 calls to delete each link
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/upstream-oauth-links",
        "/upstream-oauth-links",
        "/upstream-oauth-links",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_remove_upstream_oauth_links_when_user_has_no_link() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
        (
            "GET",
            "/api/admin/v1/upstream-oauth-links",
            mock_response_with_json(UPSTREAM_OAUTH_LINKS_EMPTY),  # type: ignore
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_upstream_oauth_links @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to get the mas user id on MAS
    # 1 call to find upstream OAuth links (no DELETE calls)
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/upstream-oauth-links",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_upstream_oauth_links_when_api_in_error() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_upstream_oauth_links @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove upstream OAuth links of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_remove_upstream_oauth_links() -> None:
    await assert_non_local_user_rejected(
        "!remove_upstream_oauth_links @user_to_reset:example2.org"
    )
