from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
    find_request,
)
from tests.matrix_admin_bot.commands.next import (
    mock_policy_data_response,
    mock_response_error,
    mock_response_with_json,
)

SERVER = "example.org"
OTHER_INSTANCE = "education.gouv.fr"
KEY = "register_proconnect_only_domains"
VALUE = "^agent-"
EXISTING_VALUE = "^existing-"


@pytest.mark.asyncio
async def test_policy_remove() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: [EXISTING_VALUE, VALUE]})
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_remove {KEY} {VALUE} {SERVER}"
    )

    # A single GET of the current policy data, then a single POST
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {"data": {KEY: [EXISTING_VALUE]}}
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/api/admin/v1/policy-data/latest",
        "/api/admin/v1/policy-data",
        reset=False,
    )

    mocked_matrix_client.check_sent_message("has been **removed**")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_remove_not_present() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: [EXISTING_VALUE]})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_remove {KEY} {VALUE} {SERVER}"
    )

    # No POST: only the GET of the current policy data
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is not in the")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_remove_missing_key() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            # No policy data has ever been set
            return mock_response_error(404, "Not Found")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_remove {KEY} {VALUE} {SERVER}"
    )

    # No POST: only the GET of the current policy data
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is not in the")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_remove_not_a_list() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: True})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_remove {KEY} {VALUE} {SERVER}"
    )

    # The current value is not a list: no POST, a clear error
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is not a list")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_remove_other_homeserver() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_remove {KEY} {VALUE} {OTHER_INSTANCE}"
    )

    # This bot is not the requested homeserver: silent no-op
    mocked_matrix_client.check_no_sent_message()
    assert mocked_matrix_client.send.await_count == 0
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_remove_invalid_syntax() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # Missing homeserver
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_remove {KEY} {VALUE}"
    )

    mocked_matrix_client.check_sent_message("Invalid syntax")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()
