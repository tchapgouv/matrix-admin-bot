from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    USER,
    mock_response_error,
    mock_response_with_json,
)


@pytest.mark.asyncio
async def test_replace_displayname() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org My-Display Name[matrix]",
    )

    # 1 call to get the mas user id on MAS
    # 1 call to change displayname on Synapse
    assert len(mock_admin_client.session.request.call_args_list) == 1  # type: ignore[reportUnknownArgumentType]
    assert len(mocked_matrix_client.send.call_args_list) == 1  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username/user_to_reset"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    assert (
        "/_synapse/admin/v2/users/@user_to_reset:example.org"
        in mocked_matrix_client.send.call_args_list[0][0][1]
    )
    assert (
        mocked_matrix_client.send.call_args_list[0][1]["data"]
        == '{"displayname": "My-Display Name[matrix]"}'
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()
    mock_admin_client.session.request.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_replace_displayname_with_single_quote() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org 'My-Display Name[matrix]'",
    )

    # 1 call to get the mas user id on MAS
    # 1 call to change displayname on Synapse
    assert len(mock_admin_client.session.request.call_args_list) == 1  # type: ignore[reportUnknownArgumentType]
    assert len(mocked_matrix_client.send.call_args_list) == 1  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username/user_to_reset"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    assert (
        "/_synapse/admin/v2/users/@user_to_reset:example.org"
        in mocked_matrix_client.send.call_args_list[0][0][1]
    )
    assert (
        mocked_matrix_client.send.call_args_list[0][1]["data"]
        == '{"displayname": "My-Display Name[matrix]"}'
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()
    mock_admin_client.session.request.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_replace_displayname_when_user_not_found() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_error(404, "Not found")
        return mock_response_error(403, "Forbidden")

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request = Mock(side_effect=request_side_effect)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org 'My-Display Name[matrix]'",
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()

    # 1 call to get the mas user id on MAS
    assert len(mock_admin_client.session.request.call_args_list) == 1  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username/user_to_reset"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    mock_admin_client.session.request.reset_mock()

    t.cancel()
