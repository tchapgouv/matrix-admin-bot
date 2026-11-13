from typing import Any
from unittest.mock import Mock

import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
    fake_synced_text_message,
)
from tests.matrix_admin_bot.commands.next import (
    mock_policy_data_response,
    mock_response_error,
)

SERVER = "example.org"
OTHER_SERVER = "other.example.org"
KEY = "register_proconnect_only_domains"
NESTED_KEY = "registration.allowed_usernames"
VALUE = "^agent-"
OTHER_KEY = "some_other_policy_key"
OTHER_VALUE = ["some_other_value"]


@pytest.mark.asyncio
async def test_policy_get() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response(
                {OTHER_KEY: OTHER_VALUE, KEY: ["ac-versailles.fr"]}
            )
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_get {KEY}"
    )

    # Read-only command: only the GET of the current policy data, no POST
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )

    msg = mocked_matrix_client.send_markdown_message.await_args_list[0][0][1]
    assert f"on homeserver `{SERVER}`" in msg
    assert '"ac-versailles.fr"' in msg

    t.cancel()


@pytest.mark.asyncio
async def test_policy_get_nested_key() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response(
                {"registration": {"allowed_usernames": [VALUE]}}
            )
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_get {NESTED_KEY}"
    )

    msg = mocked_matrix_client.send_markdown_message.await_args_list[0][0][1]
    assert f"`{NESTED_KEY}`" in msg
    assert f'"{VALUE}"' in msg

    t.cancel()


@pytest.mark.asyncio
async def test_policy_get_not_set() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            # No policy data has ever been set
            return mock_response_error(404, "Not Found")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_get {KEY}"
    )

    mocked_matrix_client.check_sent_message("is not set")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_get_get_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_response_error(500, "Internal Server Error")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_get {KEY}"
    )

    mocked_matrix_client.check_sent_message("Failed to get the current policy data")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_get_invalid_syntax() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # Missing policy key
    await mocked_matrix_client.fake_synced_text_message(room, USER1_ID, "!policy_get")

    mocked_matrix_client.check_sent_message("Invalid syntax")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_get_invalid_policy_key() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # Empty segment in the dotted key path
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!policy_get registration..allowed"
    )

    mocked_matrix_client.check_sent_message("Invalid policy key")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_get_all_servers() -> None:
    def request_side_effect1(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: ["ac-versailles.fr"]})
        return mock_response_error(403, "Forbidden")

    def request_side_effect2(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: [VALUE]})
        return mock_response_error(403, "Forbidden")

    # Two bots sharing the admin room, one per server instance
    mocked_matrix_client1, _, t1 = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client1.client_session.request.side_effect = request_side_effect1
    mocked_matrix_client2, _, t2 = await create_fake_admin_bot(
        OTHER_SERVER, is_coordinator=False, validator=OkValidator()
    )
    mocked_matrix_client2.client_session.request.side_effect = request_side_effect2

    mocked_clients = [mocked_matrix_client1, mocked_matrix_client2]
    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await fake_synced_text_message(mocked_clients, room, USER1_ID, f"!policy_get {KEY}")

    # Both bots report the value of their own homeserver
    msg1 = mocked_matrix_client1.send_markdown_message.await_args_list[0][0][1]
    assert f"on homeserver `{SERVER}`" in msg1
    assert '"ac-versailles.fr"' in msg1

    msg2 = mocked_matrix_client2.send_markdown_message.await_args_list[0][0][1]
    assert f"on homeserver `{OTHER_SERVER}`" in msg2
    assert f'"{VALUE}"' in msg2

    t1.cancel()
    t2.cancel()
