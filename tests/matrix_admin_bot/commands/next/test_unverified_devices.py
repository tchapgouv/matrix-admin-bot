from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from nio import MatrixRoom

from matrix_admin_bot.commands.next.unverified_devices import (
    UnverifiedDevicesCommand,
)
from matrix_command_bot.validation.validators.confirm import ConfirmValidator
from tests.helper import (
    USER1_ID,
    MatrixClientMock,
    check_requests_sent,
    create_fake_admin_bot,
    create_thread_relation,
    iter_requests,
)
from tests.matrix_admin_bot.commands.next import (
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)

USER_TO_RESET_ID = "@user_to_reset:example.org"
MAS_USER = {"data": {"id": "01040G2081040G2081040G2081"}}

DEVICE_ID = "AABBCCDDEE"
VERIFIED_DEVICE_ID = "FFGGHHIIJJ"

SESSION_ID = "SESSION1"
OLD_SESSION_ID = "OLD_SESSION"
NEW_SESSION_ID = "NEW_SESSION"
VERIFIED_SESSION_ID = "VERIFIED_SESSION"

COMPAT_SESSIONS_EMPTY: dict[str, Any] = {"meta": {"count": 0}, "data": []}


def synapse_devices(*device_ids: str) -> dict[str, Any]:
    return {
        "devices": [
            {"device_id": device_id, "display_name": device_id}
            for device_id in device_ids
        ]
    }


def oauth2_sessions(*sessions: tuple[str, str, str]) -> dict[str, Any]:
    """Build an oauth2 sessions response from (session_id, device_id, created_at)."""
    return {
        "meta": {"count": len(sessions)},
        "data": [
            {
                "type": "oauth2-session",
                "id": session_id,
                "attributes": {
                    "created_at": created_at,
                    "device_id": device_id,
                },
                "links": {"self": f"/api/admin/v1/oauth2-sessions/{session_id}"},
            }
            for session_id, device_id, created_at in sessions
        ],
    }


def make_request_side_effect(sessions: dict[str, Any]) -> Callable[..., Mock]:
    def request_side_effect(
        method: str,
        url: str,
        **kwargs: Any,  # noqa: ARG001
    ) -> Mock:
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(MAS_USER)
        if method == "GET" and url.endswith("/api/admin/v1/oauth2-sessions"):
            return mock_response_with_json(sessions)
        if method == "GET" and url.endswith("/api/admin/v1/compat-sessions"):
            return mock_response_with_json(COMPAT_SESSIONS_EMPTY)
        if method == "POST" and url.endswith("/finish"):
            return mock_response_with_json({})
        return mock_response_error(403, "Forbidden")

    return request_side_effect


async def run_unverified_devices(
    mocked_matrix_client: MatrixClientMock,
    command_text: str,
    unverified_devices: dict[str, str],
) -> None:
    """Run the command and reply to both validation prompts."""
    room = MatrixRoom("!roomid:example.org", USER1_ID)
    with (
        patch.object(
            UnverifiedDevicesCommand,
            "get_device_keys",
            new=AsyncMock(return_value=({}, Mock())),
        ),
        patch.object(
            UnverifiedDevicesCommand,
            "compute_unverified_devices",
            new=Mock(return_value=unverified_devices),
        ),
    ):
        command_event_id = await mocked_matrix_client.fake_synced_text_message(
            room, USER1_ID, command_text
        )
        # Validate the listing
        await mocked_matrix_client.fake_synced_text_message(
            room,
            USER1_ID,
            "yes",
            extra_content=create_thread_relation(command_event_id),
        )
        # Validate the deletion
        await mocked_matrix_client.fake_synced_text_message(
            room,
            USER1_ID,
            "yes",
            extra_content=create_thread_relation(command_event_id),
        )


def finished_session_urls(mocked_matrix_client: MatrixClientMock) -> list[str]:
    return [
        url
        for _method, url, _call in iter_requests(mocked_matrix_client.client_session)
        if url.endswith("/finish")
    ]


@pytest.mark.asyncio
async def test_unverified_devices_delete_after_validation() -> None:
    # The device is reported as unverified, so it has to be listed and
    # its sessions deleted once the command is validated.
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(synapse_devices(DEVICE_ID))
    mocked_matrix_client.client_session.request.side_effect = make_request_side_effect(
        oauth2_sessions((SESSION_ID, DEVICE_ID, "1970-01-01T00:00:00Z"))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    with (
        patch.object(
            UnverifiedDevicesCommand,
            "get_device_keys",
            new=AsyncMock(return_value=({}, Mock())),
        ),
        patch.object(
            UnverifiedDevicesCommand,
            "compute_unverified_devices",
            new=Mock(return_value={DEVICE_ID: "missing_device_keys"}),
        ),
    ):
        command_event_id = await mocked_matrix_client.fake_synced_text_message(
            room, USER1_ID, f"!unverified_devices {USER_TO_RESET_ID}"
        )

        # A validation code is required before listing the devices
        mocked_matrix_client.check_sent_message("Please reply")
        assert mocked_matrix_client.send.await_count == 0

        await mocked_matrix_client.fake_synced_text_message(
            room,
            USER1_ID,
            "yes",
            extra_content=create_thread_relation(command_event_id),
        )

        # The unverified devices are listed and reported
        mocked_matrix_client.send_file_message.assert_awaited_once()
        mocked_matrix_client.send_file_message.reset_mock()
        check_requests_sent(mocked_matrix_client.send, "/devices")

        sent_messages = [
            args[0][1]
            for args in mocked_matrix_client.send_markdown_message.await_args_list
        ]
        assert any(
            "one matching unverified device" in message for message in sent_messages
        )
        # A new validation code has to be provided to delete the sessions
        assert any("Do you want to delete" in message for message in sent_messages)

        await mocked_matrix_client.fake_synced_text_message(
            room,
            USER1_ID,
            "yes",
            extra_content=create_thread_relation(command_event_id),
        )

        # Sessions of the unverified device have been deleted
        check_requests_sent(
            mocked_matrix_client.client_session,
            "/users/by-username",
            "/oauth2-sessions",
            "/compat-sessions",
            f"/oauth2-sessions/{SESSION_ID}/finish",
        )
        mocked_matrix_client.check_sent_reactions("✏️", "🚀", "✏️", "✅")

    t.cancel()


@pytest.mark.asyncio
async def test_unverified_devices_no_deletion_when_all_verified() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(synapse_devices(DEVICE_ID))

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    with (
        patch.object(
            UnverifiedDevicesCommand,
            "get_device_keys",
            new=AsyncMock(return_value=({}, Mock())),
        ),
        patch.object(
            UnverifiedDevicesCommand,
            "compute_unverified_devices",
            new=Mock(return_value={}),
        ),
    ):
        command_event_id = await mocked_matrix_client.fake_synced_text_message(
            room, USER1_ID, f"!unverified_devices {USER_TO_RESET_ID}"
        )

        # A validation code is required before listing the devices
        mocked_matrix_client.check_sent_message("Please reply")

        await mocked_matrix_client.fake_synced_text_message(
            room,
            USER1_ID,
            "yes",
            extra_content=create_thread_relation(command_event_id),
        )

        # Nothing to report, so no report and no deletion prompt
        mocked_matrix_client.send_file_message.assert_not_awaited()
        sent_messages = [
            args[0][1]
            for args in mocked_matrix_client.send_markdown_message.await_args_list
        ]
        assert not any(
            "one matching unverified device" in message for message in sent_messages
        )
        assert not any("Do you want to delete" in message for message in sent_messages)
        assert mocked_matrix_client.client_session.request.await_count == 0
        mocked_matrix_client.check_sent_reactions("✏️", "🚀", "✅")

    t.cancel()


@pytest.mark.asyncio
async def test_unverified_devices_does_not_delete_verified_device_sessions() -> None:
    # DEVICE_ID is unverified while VERIFIED_DEVICE_ID is verified: only the
    # sessions of the unverified device may be deleted.
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(
        synapse_devices(DEVICE_ID, VERIFIED_DEVICE_ID)
    )
    mocked_matrix_client.client_session.request.side_effect = make_request_side_effect(
        oauth2_sessions(
            (SESSION_ID, DEVICE_ID, "1970-01-01T00:00:00Z"),
            (VERIFIED_SESSION_ID, VERIFIED_DEVICE_ID, "1970-01-01T00:00:00Z"),
        )
    )

    await run_unverified_devices(
        mocked_matrix_client,
        f"!unverified_devices {USER_TO_RESET_ID}",
        {DEVICE_ID: "missing_device_keys"},
    )

    urls = [
        url
        for _method, url, _call in iter_requests(mocked_matrix_client.client_session)
    ]
    assert all(VERIFIED_SESSION_ID not in url for url in urls)
    assert finished_session_urls(mocked_matrix_client) == [
        f"/api/admin/v1/oauth2-sessions/{SESSION_ID}/finish"
    ]
    mocked_matrix_client.check_sent_reactions("✏️", "🚀", "✏️", "✅")

    t.cancel()


@pytest.mark.asyncio
async def test_unverified_devices_created_after_excludes_old_sessions() -> None:
    # The only unverified session is older than created_after: nothing is
    # reported nor deleted.
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(synapse_devices(DEVICE_ID))
    mocked_matrix_client.client_session.request.side_effect = make_request_side_effect(
        oauth2_sessions((SESSION_ID, DEVICE_ID, "1970-01-01T00:00:00Z"))
    )

    await run_unverified_devices(
        mocked_matrix_client,
        f"!unverified_devices created_after=2020-01-01 {USER_TO_RESET_ID}",
        {DEVICE_ID: "missing_device_keys"},
    )

    mocked_matrix_client.send_file_message.assert_not_awaited()
    assert finished_session_urls(mocked_matrix_client) == []
    mocked_matrix_client.check_sent_reactions("✏️", "🚀", "✅")

    t.cancel()


@pytest.mark.asyncio
async def test_unverified_devices_created_after_only_deletes_new_sessions() -> None:
    # The unverified device has an old and a new session: only the session
    # created after created_after is deleted.
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(synapse_devices(DEVICE_ID))
    mocked_matrix_client.client_session.request.side_effect = make_request_side_effect(
        oauth2_sessions(
            (OLD_SESSION_ID, DEVICE_ID, "1970-01-01T00:00:00Z"),
            (NEW_SESSION_ID, DEVICE_ID, "2021-01-01T00:00:00Z"),
        )
    )

    await run_unverified_devices(
        mocked_matrix_client,
        f"!unverified_devices created_after=2020-01-01 {USER_TO_RESET_ID}",
        {DEVICE_ID: "missing_device_keys"},
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    assert finished_session_urls(mocked_matrix_client) == [
        f"/api/admin/v1/oauth2-sessions/{NEW_SESSION_ID}/finish"
    ]
    mocked_matrix_client.check_sent_reactions("✏️", "🚀", "✏️", "✅")

    t.cancel()
