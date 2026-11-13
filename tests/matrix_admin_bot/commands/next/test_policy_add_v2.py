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
NESTED_KEY = "registration.allowed_usernames"
VALUE = "^agent-"
EXISTING_VALUE = "^existing-"
OTHER_KEY = "some_other_policy_key"
OTHER_VALUE = ["some_other_value"]


@pytest.mark.asyncio
async def test_policy_add() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            # No policy data has ever been set
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    # The homeserver is explicit: the identity server is never queried
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE} {SERVER}"
    )

    # The identity server has not been queried
    assert mocked_matrix_client.send.await_count == 0

    # A single GET of the current policy data, then a single POST
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {"data": {KEY: [VALUE]}}
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/api/admin/v1/policy-data/latest",
        "/api/admin/v1/policy-data",
        reset=False,
    )

    mocked_matrix_client.check_sent_message("has been **added**")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_nested_key_keeps_other_policy_data() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response(
                {
                    OTHER_KEY: OTHER_VALUE,
                    "registration": {
                        "other_setting": True,
                        "allowed_usernames": [EXISTING_VALUE],
                    },
                }
            )
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {NESTED_KEY} {VALUE} {SERVER}"
    )

    # The other policy data keys are preserved, the new value is appended
    # to the nested list
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {
        "data": {
            OTHER_KEY: OTHER_VALUE,
            "registration": {
                "other_setting": True,
                "allowed_usernames": [EXISTING_VALUE, VALUE],
            },
        }
    }

    mocked_matrix_client.check_sent_message("has been **added**")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_already_present() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: [VALUE]})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE} {SERVER}"
    )

    # No POST: only the GET of the current policy data
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is already in the")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_not_a_list() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({KEY: True})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE} {SERVER}"
    )

    # The current value is not a list: no POST, a clear error
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is not a list")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_other_homeserver() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE} {OTHER_INSTANCE}"
    )

    # This bot is not the requested homeserver: silent no-op, and the
    # identity server has not been queried
    mocked_matrix_client.check_no_sent_message()
    assert mocked_matrix_client.send.await_count == 0
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_invalid_syntax() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # Missing homeserver
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE}"
    )

    mocked_matrix_client.check_sent_message("Invalid syntax")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_invalid_policy_key() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # Empty segment in the dotted key path
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add registration..allowed {VALUE} {SERVER}"
    )

    mocked_matrix_client.check_sent_message("Invalid policy key")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_valid_regex() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            # No policy data has ever been set
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # An escaped dot is supported by the policy regex engine (RE2)
    domain_regexp = "ac-versailles\\.fr"
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {domain_regexp} {SERVER}"
    )

    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {"data": {KEY: [domain_regexp]}}

    mocked_matrix_client.check_sent_message("has been **added**")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_unsupported_regex() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # A lookahead compiles in Python but is not supported by the policy
    # regex engine (RE2): it would break the policy evaluation on the MAS
    # side
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} ac-(?=test)fr {SERVER}"
    )

    mocked_matrix_client.check_sent_message("not supported")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_get_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_response_error(500, "Internal Server Error")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE} {SERVER}"
    )

    mocked_matrix_client.check_sent_message("Failed to get the current policy data")

    t.cancel()


@pytest.mark.asyncio
async def test_policy_add_post_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_error(403, "Forbidden")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!policy_add {KEY} {VALUE} {SERVER}"
    )

    mocked_matrix_client.check_sent_message("Failed to update the policy data")

    t.cancel()
