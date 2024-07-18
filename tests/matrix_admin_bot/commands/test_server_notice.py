from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from matrix_admin_bot.commands.server_notice import ServerNoticeCommand
from tests import (USER1_ID, USER2_ID, USER3_ID, USER4_ID, OkValidatorWithPrompt, create_fake_command_bot,
                   create_thread_relation)

user_response_data = {
    "total": 4,
    "users": [
        {'name': USER1_ID, 'user_type': None, 'is_guest': False, 'admin': True, 'deactivated': False,
         'shadow_banned': False, 'displayname': 'user1', 'avatar_url': None, 'creation_ts': 1718128165000,
         'approved': True, 'erased': False, 'last_seen_ts': 1721288374090, 'locked': False},
        {'name': USER2_ID, 'user_type': None, 'is_guest': False, 'admin': True, 'deactivated': False,
         'shadow_banned': False, 'displayname': 'user2', 'avatar_url': None, 'creation_ts': 1718127825000,
         'approved': True, 'erased': False, 'last_seen_ts': 1721288325131, 'locked': False},
        {'name': USER3_ID, 'user_type': None, 'is_guest': False, 'admin': False, 'deactivated': False,
         'shadow_banned': False, 'displayname': 'user3', 'avatar_url': None, 'creation_ts': 1718182110000,
         'approved': True, 'erased': False, 'last_seen_ts': None, 'locked': False},
        {'name': USER4_ID, 'user_type': None, 'is_guest': False, 'admin': False, 'deactivated': False,
         'shadow_banned': False, 'displayname': 'user4', 'avatar_url': None, 'creation_ts': 1718182121000,
         'approved': True, 'erased': False, 'last_seen_ts': 1720145274734, 'locked': False}
    ]
}


@pytest.mark.asyncio()
async def test_server_notice_to_all_recipients() -> None:
    mocked_client, t = await create_fake_command_bot([ServerNoticeCommand], secure_validator=OkValidatorWithPrompt())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "all",
        content={"body": "all"} | create_thread_relation(msg_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "Dear **friends** of Element",
        content={"body": "Dear **friends** of Element",
                 "format": "org.matrix.custom.html",
                 "formatted_body": "Dear <strong>Friend</strong>"}
                | create_thread_relation(msg_event_id),
    )

    mocked_client.check_sent_message("Dear **friends** of Element")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        content=create_thread_relation(msg_event_id),
    )
    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    # one call to fetch the users, and 4 calls(one per user) to send the notice to all user
    assert len(mocked_client.send.await_args_list) == 5
    assert "/users" in mocked_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[1][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[2][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[3][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[4][0][1]
    mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio()
async def test_server_notice_to_one_recipient() -> None:
    mocked_client, t = await create_fake_command_bot([ServerNoticeCommand], secure_validator=OkValidatorWithPrompt())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, USER2_ID,
        content={"body": USER2_ID} | create_thread_relation(msg_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "Dear **friends** of Element",
        content={"body": "Dear **friends** of Element",
                 "format": "org.matrix.custom.html",
                 "formatted_body": "Dear <strong>Friend</strong>"}
                | create_thread_relation(msg_event_id),
    )

    mocked_client.check_sent_message("Dear **friends** of Element")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        content=create_thread_relation(msg_event_id),
    )

    # send the report a result
    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()
    # no call to fetch the users, and one call to send the notice directly to the user
    assert len(mocked_client.send.await_args_list) == 1
    assert "/users" not in mocked_client.send.await_args_list[0][0][1]
    assert "/send_server_notice" in mocked_client.send.await_args_list[0][0][1]
    mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio()
async def test_failed_server_notice_with_no_matrix_id() -> None:
    mocked_client, t = await create_fake_command_bot([ServerNoticeCommand], secure_validator=OkValidatorWithPrompt())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value=user_response_data))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "user_not_a_matrix_id",
        content={"body": "user_not_a_matrix_id"} | create_thread_relation(msg_event_id),
    )
    mocked_client.check_sent_message("Type your notice")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "Dear **friends** of Element",
        content={"body": "Dear **friends** of Element",
                 "format": "org.matrix.custom.html",
                 "formatted_body": "Dear <strong>Friend</strong>"}
                | create_thread_relation(msg_event_id),
    )

    mocked_client.check_sent_message("Dear **friends** of Element")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        content=create_thread_relation(msg_event_id),
    )

    # no call to any endpoint if user is not a matrix id
    assert len(mocked_client.send.await_args_list) == 0
    mocked_client.send.reset_mock()

    t.cancel()
    pass
