import json
from unittest.mock import AsyncMock, Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from nio import MatrixRoom

from matrix_admin_bot.commands.server_notice import USER_ALL
from matrix_command_bot.validation.validators.confirm import ConfirmValidator
from tests import (
    USER1_ID,
    USER2_ID,
    USER3_ID,
    USER4_ID,
    create_fake_admin_bot_with_mas_enabled,
    create_replace_relation,
    create_thread_relation,
    fake_synced_text_message,
)

user_response_data = {
    "total": 4,
    "users": [
        {
            "name": USER1_ID,
            "user_type": None,
            "is_guest": False,
            "admin": True,
            "deactivated": False,
            "shadow_banned": False,
            "displayname": "user1",
            "avatar_url": None,
            "creation_ts": 1718128165000,
            "approved": True,
            "erased": False,
            "last_seen_ts": 1721288374090,
            "locked": False,
        },
        {
            "name": USER2_ID,
            "user_type": None,
            "is_guest": False,
            "admin": True,
            "deactivated": False,
            "shadow_banned": False,
            "displayname": "user2",
            "avatar_url": None,
            "creation_ts": 1718127825000,
            "approved": True,
            "erased": False,
            "last_seen_ts": 1721288325131,
            "locked": False,
        },
        {
            "name": USER3_ID,
            "user_type": None,
            "is_guest": False,
            "admin": False,
            "deactivated": False,
            "shadow_banned": False,
            "displayname": "user3",
            "avatar_url": None,
            "creation_ts": 1718182110000,
            "approved": True,
            "erased": False,
            "last_seen_ts": None,
            "locked": False,
        },
        {
            "name": USER4_ID,
            "user_type": None,
            "is_guest": False,
            "admin": False,
            "deactivated": False,
            "shadow_banned": False,
            "displayname": "user4",
            "avatar_url": None,
            "creation_ts": 1718182121000,
            "approved": True,
            "erased": False,
            "last_seen_ts": 1720145274734,
            "locked": False,
        },
    ],
}


TEXT_DATA = "Some simple server notice"


@pytest.mark.asyncio
async def test_server_notice_to_all_recipients(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=ConfirmValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_matrix_client.check_sent_message("Type your recipients with space separated")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        USER_ALL,
        extra_content=create_thread_relation(command_event_id),
    )
    mocked_matrix_client.check_sent_message("Type your notice")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        TEXT_DATA,
        extra_content=create_thread_relation(command_event_id),
    )

    mocked_matrix_client.check_sent_message("Please reply")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )
    # send the report a result
    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    # one call to fetch the users, and 4 calls(one per user) to send the notice
    # to all users
    assert len(mocked_matrix_client.send.await_args_list) == 5
    assert "/users" in mocked_matrix_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_matrix_client.send.await_args_list[1][0][1]
    assert "/send_server_notice" in mocked_matrix_client.send.await_args_list[2][0][1]
    assert "/send_server_notice" in mocked_matrix_client.send.await_args_list[3][0][1]
    assert "/send_server_notice" in mocked_matrix_client.send.await_args_list[4][0][1]
    mocked_matrix_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_html_server_notice_to_one_recipient(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=ConfirmValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_matrix_client.check_sent_message("Type your recipients with space separated")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        USER2_ID,
        extra_content=create_thread_relation(command_event_id),
    )
    mocked_matrix_client.check_sent_message("Type your notice")

    text_data = "Some **formatted** server notice"
    html_formatted_data = "Some <strong>formatted</strong> server notice"
    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        text_data,
        "org.matrix.custom.html",
        html_formatted_data,
        extra_content=create_thread_relation(command_event_id),
    )

    mocked_matrix_client.check_sent_message("Please reply")

    assert len(mocked_matrix_client.send_reaction.await_args_list) == 1
    mocked_matrix_client.send_reaction.reset_mock()

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    # send the report a result
    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert "/users" not in mocked_matrix_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_matrix_client.send.await_args_list[0][0][1]
    data = json.loads(mocked_matrix_client.send.await_args_list[0][1]["data"])
    assert data["content"]["body"] == text_data
    assert data["content"]["formatted_body"] == html_formatted_data
    mocked_matrix_client.send.reset_mock()

    assert len(mocked_matrix_client.send_reaction.await_args_list) == 2

    t.cancel()


@pytest.mark.asyncio
async def test_failed_server_notice_with_no_matrix_id(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=ConfirmValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_matrix_client.check_sent_message("Type your recipients with space separated")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "user_not_a_matrix_id",
        extra_content=create_thread_relation(msg_event_id),
    )
    mocked_matrix_client.check_sent_message("Type your notice")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        TEXT_DATA,
        extra_content=create_thread_relation(msg_event_id),
    )

    mocked_matrix_client.check_sent_message("Please reply")

    assert len(mocked_matrix_client.send_reaction.await_args_list) == 1
    mocked_matrix_client.send_reaction.reset_mock()

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(msg_event_id),
    )

    # no call to any endpoint if user is not a matrix id
    assert len(mocked_matrix_client.send.await_args_list) == 0
    mocked_matrix_client.send.reset_mock()

    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_server_notice_with_edit(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, secure_validator=ConfirmValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_matrix_client.check_sent_message("Type your recipients with space separated")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        USER2_ID,
        extra_content=create_thread_relation(msg_event_id),
    )
    mocked_matrix_client.check_sent_message("Type your notice")

    original_event_id = await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "Wrong message",
        extra_content=create_thread_relation(msg_event_id),
    )

    mocked_matrix_client.check_sent_message("Please reply")

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "* Second wrong message",
        extra_content={
            "m.new_content": {
                "msgtype": "m.text",
                "body": "Second wrong message",
            },
            **create_replace_relation(original_event_id),
        },
    )

    mocked_matrix_client.send.assert_not_awaited()

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        f"* {TEXT_DATA}",
        extra_content={
            "m.new_content": {
                "msgtype": "m.text",
                "body": TEXT_DATA,
            },
            **create_replace_relation(original_event_id),
        },
    )

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(msg_event_id),
    )

    # send the report a result
    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert "/users" not in mocked_matrix_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_matrix_client.send.await_args_list[0][0][1]
    data = json.loads(mocked_matrix_client.send.await_args_list[0][1]["data"])
    assert data["content"]["body"] == TEXT_DATA
    mocked_matrix_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_to_one_recipient_with_coordinator(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client1,
        _,
        t1,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, "example.org", secure_validator=ConfirmValidator()
    )
    mocked_matrix_client1.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    (
        mocked_matrix_client2,
        _,
        t2,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch,
        "example2.org",
        secure_validator=ConfirmValidator(),
        is_coordinator=False,
    )
    mocked_matrix_client2.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mocked_matrix_clients = [mocked_matrix_client1, mocked_matrix_client2]

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await fake_synced_text_message(
        mocked_matrix_clients, room, USER1_ID, "!server_notice"
    )

    mocked_matrix_client1.check_sent_message(
        "Type your recipients with space separated"
    )
    mocked_matrix_client2.check_no_sent_message()

    await fake_synced_text_message(
        mocked_matrix_clients,
        room,
        USER1_ID,
        "@user:example2.org",
        extra_content=create_thread_relation(command_event_id),
    )
    mocked_matrix_client1.check_sent_message("Type your notice")
    mocked_matrix_client2.check_no_sent_message()

    await fake_synced_text_message(
        mocked_matrix_clients,
        room,
        USER1_ID,
        TEXT_DATA,
        extra_content=create_thread_relation(command_event_id),
    )

    mocked_matrix_client1.check_sent_message("Please reply")

    mocked_matrix_client1.check_sent_reactions("✏️")
    assert len(mocked_matrix_client2.send_reaction.await_args_list) == 0

    await fake_synced_text_message(
        mocked_matrix_clients,
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    mocked_matrix_client1.check_sent_reactions()
    assert len(mocked_matrix_client1.room_redact.await_args_list) == 1
    mocked_matrix_client2.check_sent_reactions("🚀", "✅")

    assert len(mocked_matrix_client1.send.await_args_list) == 0

    # send the report a result
    mocked_matrix_client2.send_file_message.assert_awaited_once()
    mocked_matrix_client2.send_file_message.reset_mock()

    assert "/send_server_notice" in mocked_matrix_client2.send.await_args_list[0][0][1]

    t1.cancel()
    t2.cancel()
