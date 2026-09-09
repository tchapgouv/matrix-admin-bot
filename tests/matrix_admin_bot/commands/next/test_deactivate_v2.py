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
    COMPAT_SESSIONS_LIST,
    OAUTH2_SESSIONS_LIST,
    USER,
    USER_SESSIONS_LIST,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_deactivate() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/compat-sessions"):
            return mock_response_with_json(COMPAT_SESSIONS_LIST)
        if method == "GET" and url.endswith("/api/admin/v1/oauth2-sessions"):
            return mock_response_with_json(OAUTH2_SESSIONS_LIST)
        if method == "GET" and url.endswith("/api/admin/v1/user-sessions"):
            return mock_response_with_json(USER_SESSIONS_LIST)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!deactivate @user_to_reset:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # one call to fetch the devices
    check_requests_sent(mocked_matrix_client.send, "/devices")
    # 1 call to get the mas user id on MAS
    # 3 calls to get each session type
    # 1 call to deactivate user
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/compat-sessions",
        "/user-sessions",
        "/oauth2-sessions",
        "/deactivate",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_deactivate() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_error(404, "Not found")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!deactivate @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message("Couldn't deactivate")

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_deactivate() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!deactivate @user_to_reset:example2.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
