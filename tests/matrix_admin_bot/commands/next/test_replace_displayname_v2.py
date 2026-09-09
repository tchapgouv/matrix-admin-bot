from typing import Any
from unittest.mock import Mock

import pytest
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
    find_request,
)
from tests.matrix_admin_bot.commands.next import (
    USER,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_replace_displayname() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org My-Display Name[matrix]",
    )

    # 1 call to get the mas user id on MAS
    # 1 call to change displayname on Synapse
    displayname_request = find_request(
        mocked_matrix_client.send,
        "PUT",
        "/_synapse/admin/v2/users/@user_to_reset:example.org",
    )
    assert (
        displayname_request.kwargs["data"]
        == '{"displayname": "My-Display Name[matrix]"}'
    )
    check_requests_sent(
        mocked_matrix_client.send,
        "/_synapse/admin/v2/users/@user_to_reset:example.org",
    )
    check_requests_sent(mocked_matrix_client.client_session, "/users/by-username")

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_replace_displayname_with_single_quote() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org 'My-Display Name[matrix]'",
    )

    # 1 call to get the mas user id on MAS
    # 1 call to change displayname on Synapse
    displayname_request = find_request(
        mocked_matrix_client.send,
        "PUT",
        "/_synapse/admin/v2/users/@user_to_reset:example.org",
    )
    assert (
        displayname_request.kwargs["data"]
        == '{"displayname": "My-Display Name[matrix]"}'
    )
    check_requests_sent(
        mocked_matrix_client.send,
        "/_synapse/admin/v2/users/@user_to_reset:example.org",
    )
    check_requests_sent(mocked_matrix_client.client_session, "/users/by-username")

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_replace_displayname_when_user_not_found() -> None:
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
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org 'My-Display Name[matrix]'",
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # 1 call to get the mas user id on MAS
    check_requests_sent(mocked_matrix_client.client_session, "/users/by-username")

    t.cancel()
