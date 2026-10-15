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
    find_request,
)
from tests.matrix_admin_bot.commands.next import (
    mock_get_homeserver,
    mock_policy_data_response,
    mock_response_error,
    mock_response_with_json,
)

DOMAIN = "ac-versailles\\.fr"
EXISTING_DOMAIN = "existing-domain\\.fr"
OTHER_KEY = "some_other_policy_key"
OTHER_VALUE = ["some_other_value"]


@pytest.mark.asyncio
async def test_register_remove_proconnect_only_domain() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response(
                {OTHER_KEY: OTHER_VALUE, POLICY_DATA_KEY: [DOMAIN, EXISTING_DOMAIN]}
            )
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    # The identity server says that this email domain is in the charge of
    # this bot's homeserver
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_remove_proconnect_only_domain {DOMAIN}"
    )

    # The other policy data keys are preserved, the domain is removed
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {
        "data": {
            OTHER_KEY: OTHER_VALUE,
            POLICY_DATA_KEY: [EXISTING_DOMAIN],
        }
    }

    mocked_matrix_client.check_sent_message("has been **removed**")

    t.cancel()


@pytest.mark.asyncio
async def test_register_remove_proconnect_only_domain_not_present() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({POLICY_DATA_KEY: [EXISTING_DOMAIN]})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_remove_proconnect_only_domain {DOMAIN}"
    )

    # No POST: only the GET of the current policy data
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is not in the")

    t.cancel()


@pytest.mark.asyncio
async def test_register_remove_proconnect_only_domain_last_domain() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({POLICY_DATA_KEY: [DOMAIN]})
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_remove_proconnect_only_domain {DOMAIN}"
    )

    # Removing the last domain results in an empty list
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {"data": {POLICY_DATA_KEY: []}}

    mocked_matrix_client.check_sent_message("has been **removed**")

    t.cancel()
