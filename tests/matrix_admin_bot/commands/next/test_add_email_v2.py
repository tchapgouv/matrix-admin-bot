from typing import Any
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
    USER,
    USER_EMAIL,
    USER_EMAILS_LIST,
    mock_response_error,
    mock_response_with_json,
)


@pytest.mark.asyncio
async def test_add_email(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAIL)
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)
    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()

    # 1 call to get the mas user id on MAS
    # 1 call to check if email is not used
    # 1 call to check if user has no email
    # 1 call to add email
    assert len(mock_admin_client.session.request.call_args_list) == 4  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[1][0][1]
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[2][0][1]
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[3][0][1]
    mock_admin_client.session.request.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_add_email_when_email_already_used(
    monkeypatch: MonkeyPatch,
) -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if (
            method == "GET"
            and url.endswith("/api/admin/v1/user-emails")
            and "filter[email]" in kwargs["params"]
        ):
            # Some user is already using this email
            return mock_response_with_json(USER_EMAILS_LIST)
        if method == "POST" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAIL)

        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message("Couldn't add email the following users:")

    t.cancel()


@pytest.mark.asyncio
async def test_failed_add_email_when_user_has_email(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if (
            method == "GET"
            and url.endswith("/api/admin/v1/user-emails")
            and "filter[user]" in kwargs["params"]
        ):
            # Our user is already using this email
            return mock_response_with_json(USER_EMAILS_LIST)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_error(404, "Not found")
        if method == "POST" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAIL)

        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message("Couldn't add email the following users:")

    t.cancel()


@pytest.mark.asyncio
async def test_failed_add_email_when_api_in_error(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request.return_value = mock_response_error(
        403, "Forbidden"
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example.org user@domain.tld"
    )

    mocked_matrix_client.check_sent_message("Couldn't add email the following users:")

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_add_email(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!add_email @user_to_reset:example2.org user@domain.tld"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
