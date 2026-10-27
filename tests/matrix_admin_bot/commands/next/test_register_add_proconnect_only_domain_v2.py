from typing import Any
from unittest.mock import AsyncMock, Mock

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

SERVER = "example.org"
OTHER_INSTANCE = "education.gouv.fr"
CATCH_ALL = ".*"
DOMAIN = "ac-versailles\\.fr"
PROBE_EMAIL = "tchap.bot.probe@ac-versailles.fr"
EXISTING_DOMAIN = "existing-domain\\.fr"
OTHER_KEY = "some_other_policy_key"
OTHER_VALUE = ["some_other_value"]


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            # No policy data has ever been set
            return mock_response_error(404, "Not Found")
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
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    # The homeserver in charge of the domain has been guessed from the
    # identity server, with a dummy email on the plain domain
    assert len(mocked_matrix_client.send.await_args_list) == 1
    info_url = mocked_matrix_client.send.await_args_list[0][0][1]
    assert info_url.startswith("/_matrix/identity/api/v1/info")
    assert f"address={PROBE_EMAIL}" in info_url

    # A single GET of the current policy data, then a single POST
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {"data": {POLICY_DATA_KEY: [DOMAIN]}}
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/api/admin/v1/policy-data/latest",
        "/api/admin/v1/policy-data",
        reset=False,
    )

    mocked_matrix_client.check_sent_message("has been **added**")

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_keeps_other_policy_data() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response(
                {OTHER_KEY: OTHER_VALUE, POLICY_DATA_KEY: [EXISTING_DOMAIN]}
            )
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_with_json({"data": {}})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    # The other policy data keys are preserved, the new domain is appended
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {
        "data": {
            OTHER_KEY: OTHER_VALUE,
            POLICY_DATA_KEY: [EXISTING_DOMAIN, DOMAIN],
        }
    }

    mocked_matrix_client.check_sent_message("has been **added**")

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_already_present() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_policy_data_response({POLICY_DATA_KEY: [DOMAIN]})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    # No POST: only the GET of the current policy data
    check_requests_sent(
        mocked_matrix_client.client_session, "/api/admin/v1/policy-data/latest"
    )
    mocked_matrix_client.check_sent_message("is already in the")

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_other_instance() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    # The identity server says that this email domain is in the charge of
    # another homeserver: the bot of this other homeserver executes the
    # command
    mocked_matrix_client.send = mock_get_homeserver(OTHER_INSTANCE)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    # This bot is not in charge of this domain: silent no-op
    mocked_matrix_client.check_no_sent_message()
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_unknown_domain() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    # The identity server does not know this email domain
    mocked_matrix_client.send = mock_get_homeserver(None)

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    # No homeserver is in charge of this domain: silent no-op
    mocked_matrix_client.check_no_sent_message()
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_invalid_syntax() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!register_add_proconnect_only_domain domain homeserver extra",
    )

    mocked_matrix_client.check_sent_message("Invalid syntax")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_invalid_regexp() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!register_add_proconnect_only_domain [unclosed"
    )

    mocked_matrix_client.check_sent_message("Invalid domain regexp")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_unsupported_regexp() -> None:
    # A lookahead compiles in Python but is not supported by the policy
    # regex engine (RE2)
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!register_add_proconnect_only_domain ac-(?=test)fr"
    )

    mocked_matrix_client.check_sent_message("not supported")
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_get_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_response_error(500, "Internal Server Error")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    mocked_matrix_client.check_sent_message("Failed to get the current policy data")

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_post_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith("/api/admin/v1/policy-data/latest"):
            return mock_response_error(404, "Not Found")
        if method == "POST" and url.endswith("/api/admin/v1/policy-data"):
            return mock_response_error(403, "Forbidden")
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_get_homeserver("example.org")
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {DOMAIN}"
    )

    mocked_matrix_client.check_sent_message("Failed to update the policy data")

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_explicit_homeserver() -> None:
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

    # A catch-all regexp cannot be classified by the identity server: the
    # homeserver is given explicitly
    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, f"!register_add_proconnect_only_domain {CATCH_ALL} {SERVER}"
    )

    # The identity server has not been queried
    assert mocked_matrix_client.send.await_count == 0
    post_call = find_request(
        mocked_matrix_client.client_session, "POST", "/api/admin/v1/policy-data"
    )
    assert post_call.kwargs["json"] == {"data": {POLICY_DATA_KEY: [CATCH_ALL]}}

    mocked_matrix_client.check_sent_message("has been **added**")

    t.cancel()


@pytest.mark.asyncio
async def test_register_add_proconnect_only_domain_explicit_other_homeserver() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    # A catch-all regexp for another homeserver
    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        f"!register_add_proconnect_only_domain {CATCH_ALL} {OTHER_INSTANCE}",
    )

    # This bot is not the requested homeserver: silent no-op, and the
    # identity server has not been queried
    mocked_matrix_client.check_no_sent_message()
    assert mocked_matrix_client.send.await_count == 0
    assert len(mocked_matrix_client.client_session.request.await_args_list) == 0

    t.cancel()
