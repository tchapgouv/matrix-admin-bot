from typing import Any
from unittest.mock import Mock

import pytest
from nio import MatrixRoom

from matrix_admin_bot.commands.next.register_proconnect_only_domain import (
    POLICY_DATA_KEY,
)
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
DOMAIN = "ac-versailles\\.fr"
EXISTING_DOMAIN = "existing-domain\\.fr"
OTHER_KEY = "some_other_policy_key"
OTHER_VALUE = ["some_other_value"]


@pytest.mark.asyncio
async def test_register_list_proconnect_only_domains() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response(
                {OTHER_KEY: OTHER_VALUE, POLICY_DATA_KEY: [DOMAIN, EXISTING_DOMAIN]}
            )
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!register_list_proconnect_only_domains"
    )

    # Read-only command: only the GET of the current policy data, no POST
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )

    msg = mocked_matrix_client.send_markdown_message.await_args_list[0][0][1]
    assert f"of homeserver `{SERVER}`" in msg
    assert f"- `{DOMAIN}`" in msg
    assert f"- `{EXISTING_DOMAIN}`" in msg

    t.cancel()


@pytest.mark.asyncio
async def test_register_list_proconnect_only_domains_empty() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            # No policy data has ever been set
            return mock_response_error(404, "Not Found")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!register_list_proconnect_only_domains"
    )

    mocked_matrix_client.check_sent_message("No ProConnect-only domain is set")

    t.cancel()


@pytest.mark.asyncio
async def test_register_list_proconnect_only_domains_get_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_response_error(500, "Internal Server Error")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!register_list_proconnect_only_domains"
    )

    mocked_matrix_client.check_sent_message("Failed to get the current policy data")

    t.cancel()


@pytest.mark.asyncio
async def test_register_list_proconnect_only_domains_invalid_syntax() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!register_list_proconnect_only_domains extra-arg"
    )

    mocked_matrix_client.check_sent_message("Invalid syntax")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_register_list_proconnect_only_domains_all_servers() -> None:
    def request_side_effect1(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({POLICY_DATA_KEY: [DOMAIN]})
        return mock_response_error(403, "Forbidden")

    def request_side_effect2(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({POLICY_DATA_KEY: [EXISTING_DOMAIN]})
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

    await fake_synced_text_message(
        mocked_clients, room, USER1_ID, "!register_list_proconnect_only_domains"
    )

    # Both bots report the domains of their own homeserver
    msg1 = mocked_matrix_client1.send_markdown_message.await_args_list[0][0][1]
    assert f"of homeserver `{SERVER}`" in msg1
    assert f"- `{DOMAIN}`" in msg1

    msg2 = mocked_matrix_client2.send_markdown_message.await_args_list[0][0][1]
    assert f"of homeserver `{OTHER_SERVER}`" in msg2
    assert f"- `{EXISTING_DOMAIN}`" in msg2

    t1.cancel()
    t2.cancel()
