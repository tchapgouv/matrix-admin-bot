from unittest.mock import AsyncMock, Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    create_fake_admin_bot_with_mas_enabled,
)
from tests.matrix_admin_bot.commands.next import (
    COMPAT_SESSIONS_LIST,
    OAUTH2_SESSIONS_LIST,
    USER,
    USER_EMAIL,
    USER_SESSIONS_LIST,
    mock_response_error,
    mock_response_with_json,
)


@pytest.mark.asyncio
async def test_reactivate(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect(method: str, url: str) -> Mock:  # noqa: PLR0911
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
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAIL)
        if method == "POST" and url.endswith(
            "/api/admin/v1/users/01040G2081040G2081040G2081/reactivate"
        ):
            return mock_response_with_json(USER)
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # one call to fetch the devices
    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert "/devices" in mocked_matrix_client.send.await_args_list[0][0][1]
    mocked_matrix_client.send.reset_mock()
    # 1 call to get the mas user id on MAS
    # 3 calls to get each session type
    # 1 call to reactivate user
    # 1 call to check if email is not used
    # 1 call to check if user has no email
    # 1 call to add email
    assert len(mock_admin_client.session.request.call_args_list) == 8  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    assert (
        "/compat-sessions" in mock_admin_client.session.request.call_args_list[1][0][1]
    )
    assert "/user-sessions" in mock_admin_client.session.request.call_args_list[2][0][1]
    assert (
        "/oauth2-sessions" in mock_admin_client.session.request.call_args_list[3][0][1]
    )
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[4][0][1]
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[5][0][1]
    assert "/reactivate" in mock_admin_client.session.request.call_args_list[6][0][1]
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[7][0][1]
    mock_admin_client.session.request.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_reactivate(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect(method: str, url: str) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_error(404, "Not found")
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message("Couldn't reactivate")

    t.cancel()


@pytest.mark.asyncio
async def test_failed_reactivate_invalid_input(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect(method: str, url: str) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_error(404, "Not found")
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0
    assert len(mock_admin_client.session.request.call_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_reactivate(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reactivate @user_to_reset:example2.org user@domain.tld"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
