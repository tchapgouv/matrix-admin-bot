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
    PERSONAL_SESSIONS_LIST,
    USER,
    USER_EMAIL,
    USER_SESSIONS_LIST,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_reactivate() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001,PLR0911
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
        if method == "GET" and url.endswith("/api/admin/v1/personal-sessions"):
            return mock_response_with_json(PERSONAL_SESSIONS_LIST)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAIL)
        if method == "POST" and url.endswith(
            "/api/admin/v1/users/01040G2081040G2081040G2081/reactivate"
        ):
            return mock_response_with_json(USER)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # one call to fetch the devices
    check_requests_sent(mocked_matrix_client.send, "/devices")
    # 1 call to get the mas user id on MAS
    # 4 calls to get each session type
    # 1 call to reactivate user
    # 1 call to check if email is not used
    # 1 call to check if user has no email
    # 1 call to add email
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/compat-sessions",
        "/oauth2-sessions",
        "/user-sessions",
        "/personal-sessions",
        "/user-emails",
        "/user-emails",
        "/reactivate",
        "/user-emails",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_reactivate() -> None:
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
        room, USER1_ID, "!reactivate @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message("Couldn't reactivate")

    t.cancel()


@pytest.mark.asyncio
async def test_failed_reactivate_invalid_input() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0
    check_requests_sent(mocked_matrix_client.client_session)

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_reactivate() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example2.org user@domain.tld"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
