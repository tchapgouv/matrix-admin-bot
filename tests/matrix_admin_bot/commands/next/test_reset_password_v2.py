from unittest.mock import AsyncMock, Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from nio import MatrixRoom

from matrix_admin_bot.commands.next.admin_client import check_if_mas_enabled
from tests import USER1_ID, OkValidator, create_fake_admin_bot_with_mas_enabled


@pytest.mark.asyncio
async def test_check_if_mas_enabled(monkeypatch: MonkeyPatch) -> None:
    await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=OkValidator()
    )

    assert check_if_mas_enabled("https://example.org") is True


@pytest.mark.asyncio
async def test_reset_password_v2(monkeypatch: MonkeyPatch) -> None:
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
    mock_admin_client.session.request.return_value = Mock(
        ok=True,
        json=Mock(return_value={"meta": {"count": 1}, "data": {"id": "MAS_ID"}}),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password @user_to_reset:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # 1 call to fetch the devices on synapse
    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert "/devices" in mocked_matrix_client.send.await_args_list[0][0][1]
    mocked_matrix_client.send.reset_mock()
    # 1 call to get the mas user id on MAS
    # 3 calls to get each session type
    # 1 call to reset the password
    # 1 call to kill sessions
    assert len(mock_admin_client.session.request.call_args_list) == 6  # type: ignore[reportUnknownArgumentType]
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
    assert "/set-password" in mock_admin_client.session.request.call_args_list[4][0][1]
    assert "/kill-sessions" in mock_admin_client.session.request.call_args_list[5][0][1]
    mock_admin_client.session.request.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_reset_password_v2(monkeypatch: MonkeyPatch) -> None:
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
    mock_admin_client.session.request.return_value = Mock(
        ok=False, json=Mock(return_value={"data": {"id": "MAS_ID"}})
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message("Couldn't reset the password")

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_reset_password_v2(monkeypatch: MonkeyPatch) -> None:
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
    mock_admin_client.session.request.return_value = Mock(
        ok=True, json=Mock(return_value={"data": {"id": "MAS_ID"}})
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password @user_to_reset:example2.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0
    assert len(mock_admin_client.session.request.call_args_list) == 0  # type: ignore[reportUnknownArgumentType]

    t.cancel()
