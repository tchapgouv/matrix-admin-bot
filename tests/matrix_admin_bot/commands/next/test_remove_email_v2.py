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
    USER_EMAILS_LIST,
    USER_EMAILS_LIST_NO_DATA,
    mock_response_error,
    mock_response_with_json,
)


@pytest.mark.asyncio
async def test_remove_email(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect(method: str, url: str) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAILS_LIST)
        if method == "DELETE" and url.endswith(
            "/api/admin/v1/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09"
        ):
            return Mock(
                ok=True,
                status_code=204,
            )
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
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()

    # 1 call to get the mas user id on MAS
    # 1 call to find if user has an email
    # 1 call to remove_email user
    assert len(mock_admin_client.session.request.call_args_list) == 3  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[1][0][1]
    assert "/user-emails" in mock_admin_client.session.request.call_args_list[2][0][1]
    mock_admin_client.session.request.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_email_when_user_has_no_email(
    monkeypatch: MonkeyPatch,
) -> None:
    def request_side_effect(method: str, url: str) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            # Our user has no email
            return mock_response_with_json(USER_EMAILS_LIST_NO_DATA)
        if method == "DELETE" and url.endswith(
            "/api/admin/v1/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09"
        ):
            return Mock(
                ok=True,
                status_code=204,
            )
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
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove email the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_email_when_api_in_error(monkeypatch: MonkeyPatch) -> None:
    def request_side_effect() -> Mock:
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
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove email the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_remove_email(monkeypatch: MonkeyPatch) -> None:
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
        room, USER1_ID, "!remove_email @user_to_reset:example2.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
