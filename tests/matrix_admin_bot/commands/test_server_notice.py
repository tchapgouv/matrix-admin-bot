import json
from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from matrix_admin_bot.commands.server_notice import USER_ALL
from matrix_command_bot.validation.validators.confirm import ConfirmValidator
from tests import (
    USER1_ID,
    USER2_ID,
    USER3_ID,
    USER4_ID,
    create_fake_admin_bot,
    create_replace_relation,
    create_thread_relation,
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
async def test_server_notice_to_all_recipients() -> None:
    mocked_client, t = await create_fake_admin_bot(secure_validator=ConfirmValidator())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        USER_ALL,
        extra_content=create_thread_relation(command_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        TEXT_DATA,
        extra_content=create_thread_relation(command_event_id),
    )

    mocked_client.check_sent_message("Please reply")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )
    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    # one call to fetch the users, and 4 calls(one per user) to send the notice
    # to all users
    assert len(mocked_client.send.await_args_list) == 5
    assert "/users" in mocked_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[1][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[2][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[3][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[4][0][1]
    mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio
async def test_html_server_notice_to_one_recipient() -> None:
    mocked_client, t = await create_fake_admin_bot(secure_validator=ConfirmValidator())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        USER2_ID,
        extra_content=create_thread_relation(command_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    text_data = "Some **formatted** server notice"
    html_formatted_data = "Some <strong>formatted</strong> server notice"
    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        text_data,
        "org.matrix.custom.html",
        html_formatted_data,
        extra_content=create_thread_relation(command_event_id),
    )

    mocked_client.check_sent_message("Please reply")

    assert len(mocked_client.send_reaction.await_args_list) == 1
    mocked_client.send_reaction.reset_mock()

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_client.send.await_args_list) == 1
    assert "/users" not in mocked_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[0][0][1]
    data = json.loads(mocked_client.send.await_args_list[0][1]["data"])
    assert data["content"]["body"] == text_data
    assert data["content"]["formatted_body"] == html_formatted_data
    mocked_client.send.reset_mock()

    assert len(mocked_client.send_reaction.await_args_list) == 2

    t.cancel()


@pytest.mark.asyncio
async def test_failed_server_notice_with_no_matrix_id() -> None:
    mocked_client, t = await create_fake_admin_bot(secure_validator=ConfirmValidator())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "user_not_a_matrix_id",
        extra_content=create_thread_relation(msg_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        TEXT_DATA,
        extra_content=create_thread_relation(msg_event_id),
    )

    mocked_client.check_sent_message("Please reply")

    assert len(mocked_client.send_reaction.await_args_list) == 1
    mocked_client.send_reaction.reset_mock()

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(msg_event_id),
    )

    # no call to any endpoint if user is not a matrix id
    assert len(mocked_client.send.await_args_list) == 0
    mocked_client.send.reset_mock()

    assert len(mocked_client.send_reaction.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_server_notice_with_edit() -> None:
    mocked_client, t = await create_fake_admin_bot(secure_validator=ConfirmValidator())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        USER2_ID,
        extra_content=create_thread_relation(msg_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    original_event_id = await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "Wrong message",
        extra_content=create_thread_relation(msg_event_id),
    )

    mocked_client.check_sent_message("Please reply")

    await mocked_client.fake_synced_text_message(
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

    mocked_client.send.assert_not_awaited()

    await mocked_client.fake_synced_text_message(
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

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(msg_event_id),
    )

    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_client.send.await_args_list) == 1
    assert "/users" not in mocked_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[0][0][1]
    data = json.loads(mocked_client.send.await_args_list[0][1]["data"])
    assert data["content"]["body"] == TEXT_DATA
    mocked_client.send.reset_mock()

    t.cancel()
