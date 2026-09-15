from typing import Any
from unittest.mock import Mock

import pytest
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    UPSTREAM_OAUTH_LINKS_EMPTY,
    UPSTREAM_OAUTH_LINKS_LIST,
    USER,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_remove_upstream_oauth_links() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/upstream-oauth-links"):
            return mock_response_with_json(UPSTREAM_OAUTH_LINKS_LIST)
        if method == "DELETE" and url.endswith(
            "/api/admin/v1/upstream-oauth-links/01K5R30ZEENQQCR9ZPQY9KYP0A"
        ):
            return mock_response_with_json({})
        if method == "DELETE" and url.endswith(
            "/api/admin/v1/upstream-oauth-links/01K5R30ZEENQQCR9ZPQY9KYP0B"
        ):
            return mock_response_with_json({})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect
    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_upstream_oauth_links @user_to_reset:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()

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
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/upstream-oauth-links"):
            return mock_response_with_json(UPSTREAM_OAUTH_LINKS_EMPTY)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect
    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_upstream_oauth_links @user_to_reset:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()

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
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

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
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_upstream_oauth_links @user_to_reset:example2.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
