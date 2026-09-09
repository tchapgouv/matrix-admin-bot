import json
from typing import Any
from unittest.mock import Mock

import pytest
from nio import MatrixRoom

from matrix_admin_bot.commands.next.server_notice_v2 import USER_ALL
from matrix_command_bot.validation.validators.confirm import ConfirmValidator
from tests import (
    USER1_ID,
    USER2_ID,
    USER3_ID,
    USER4_ID,
    check_requests_sent,
    create_fake_admin_bot,
    create_replace_relation,
    create_thread_relation,
    fake_synced_text_message,
    find_request,
)
from tests.matrix_admin_bot.commands.next import (
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)

mas_user_response_data_page1 = {
    "meta": {"count": 4},
    "data": [
        {
            "type": "user",
            "id": "01040G2081040G2081040G2081",
            "attributes": {
                "username": USER1_ID,
                "created_at": "1970-01-01T00:00:00Z",
                "locked_at": "null",
                "deactivated_at": "null",
                "admin": "false",
                "legacy_guest": "false",
            },
            "links": {"self": "/api/admin/v1/users/01040G2081040G2081040G2081"},
            "meta": {"page": {"cursor": "01040G2081040G2081040G2081"}},
        },
        {
            "type": "user",
            "id": "02081040G2081040G2081040G2",
            "attributes": {
                "username": USER2_ID,
                "created_at": "1970-01-01T00:00:00Z",
                "locked_at": "null",
                "deactivated_at": "null",
                "admin": "true",
                "legacy_guest": "false",
            },
            "links": {"self": "/api/admin/v1/users/02081040G2081040G2081040G2"},
            "meta": {"page": {"cursor": "02081040G2081040G2081040G2"}},
        },
        {
            "type": "user",
            "id": "030C1G60R30C1G60R30C1G60R3",
            "attributes": {
                "username": USER3_ID,
                "created_at": "1970-01-01T00:00:00Z",
                "locked_at": "1970-01-01T00:00:00Z",
                "deactivated_at": "null",
                "admin": "false",
                "legacy_guest": "true",
            },
            "links": {"self": "/api/admin/v1/users/030C1G60R30C1G60R30C1G60R3"},
            "meta": {"page": {"cursor": "030C1G60R30C1G60R30C1G60R3"}},
        },
    ],
    "links": {
        "self": "/api/admin/v1/users?page[first]=3",
        "first": "/api/admin/v1/users?page[first]=3",
        "last": "/api/admin/v1/users?page[last]=3",
        "next": "/api/admin/v1/users?filter[status]=active"
        "&page[after]=030C1G60R30C1G60R30C1G60R3&page[first]=3",
    },
}

mas_user_response_data_page2 = {
    "meta": {"count": 4},
    "data": [
        {
            "type": "user",
            "id": "01040G2081040G2081040G2082",
            "attributes": {
                "username": USER4_ID,
                "created_at": "1970-01-01T00:00:00Z",
                "locked_at": "null",
                "deactivated_at": "null",
                "admin": "false",
                "legacy_guest": "false",
            },
            "links": {"self": "/api/admin/v1/users/01040G2081040G2081040G2081"},
            "meta": {"page": {"cursor": "01040G2081040G2081040G2081"}},
        },
    ],
    "links": {
        "self": "/api/admin/v1/users?page[first]=3",
        "first": "/api/admin/v1/users?page[first]=3",
        "last": "/api/admin/v1/users?page[last]=3",
    },
}

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
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users?filter[status]=active&page[first]=100"
        ):
            return mock_response_with_json(mas_user_response_data_page1)
        if method == "GET" and url.endswith(
            "/api/admin/v1/users?filter[status]=active&page[after]=030C1G60R30C1G60R30C1G60R3&page[first]=3"
        ):
            return mock_response_with_json(mas_user_response_data_page2)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

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
    # 2 calls to fetch the users
    check_requests_sent(mocked_matrix_client.client_session, *(["/users"] * 2))
    # 4 calls(one per user) to send the notice to all users
    check_requests_sent(mocked_matrix_client.send, *(["/send_server_notice"] * 4))

    t.cancel()


@pytest.mark.asyncio
async def test_server_notice_to_all_recipients_when_invalid_request() -> None:
    counter = 0

    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        nonlocal counter
        if method == "GET" and url.endswith(
            "/api/admin/v1/users?filter[status]=active&page[first]=100"
        ):
            return mock_response_with_json(mas_user_response_data_page1)
        if (
            method == "GET"
            and url.endswith(
                "/api/admin/v1/users?filter[status]=active&page[after]=030C1G60R30C1G60R30C1G60R3&page[first]=3"
            )
            and counter == 4
        ):
            return mock_response_with_json(mas_user_response_data_page2)
        counter += 1
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

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
    # 6 calls to fetch the users
    check_requests_sent(mocked_matrix_client.client_session, *(["/users"] * 6))
    # 4 calls(one per user) to send the notice to all users
    check_requests_sent(mocked_matrix_client.send, *(["/send_server_notice"] * 4))

    t.cancel()


@pytest.mark.asyncio
async def test_server_notice_to_all_recipients_when_exception() -> None:
    counter = 0

    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        nonlocal counter
        if method == "GET" and url.endswith(
            "/api/admin/v1/users?filter[status]=active&page[first]=100"
        ):
            return mock_response_with_json(mas_user_response_data_page1)
        if (
            method == "GET"
            and url.endswith(
                "/api/admin/v1/users?filter[status]=active&page[after]=030C1G60R30C1G60R30C1G60R3&page[first]=3"
            )
            and counter == 4
        ):
            return mock_response_with_json(mas_user_response_data_page2)
        counter += 1
        reason = "Keep having exception until it succeed"
        raise Exception(reason)

    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

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
    # 6 calls to fetch the users
    check_requests_sent(mocked_matrix_client.client_session, *(["/users"] * 6))
    # 4 calls(one per user) to send the notice to all users
    check_requests_sent(mocked_matrix_client.send, *(["/send_server_notice"] * 4))

    t.cancel()


@pytest.mark.asyncio
async def test_server_notice_to_all_recipients_failed() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users?filter[status]=active&page[first]=100"
        ):
            return mock_response_with_json(mas_user_response_data_page1)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

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
    # 6 calls to fetch the users
    check_requests_sent(mocked_matrix_client.client_session, *(["/users"] * 6))
    # no call to send the notice to all users
    check_requests_sent(mocked_matrix_client.send)

    t.cancel()


@pytest.mark.asyncio
async def test_html_server_notice_to_one_recipient() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)

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
    # no call to fetch the users
    check_requests_sent(mocked_matrix_client.client_session)
    # one call to send the notice directly to the user
    send_request = find_request(
        mocked_matrix_client.send, "POST", "/send_server_notice"
    )
    data = json.loads(send_request.kwargs["data"])
    assert data["content"]["body"] == text_data
    assert data["content"]["formatted_body"] == html_formatted_data
    check_requests_sent(mocked_matrix_client.send, "/send_server_notice")

    assert len(mocked_matrix_client.send_reaction.await_args_list) == 2

    t.cancel()


@pytest.mark.asyncio
async def test_failed_server_notice_with_no_matrix_id() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)

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
    check_requests_sent(mocked_matrix_client.client_session)
    check_requests_sent(mocked_matrix_client.send)
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()


@pytest.mark.asyncio
async def test_server_notice_with_edit() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(
        validator=ConfirmValidator()
    )
    mocked_matrix_client.send = mock_send_response(user_response_data)

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
    # no call to fetch the users
    check_requests_sent(mocked_matrix_client.client_session)
    # one call to send the notice directly to the user
    send_request = find_request(
        mocked_matrix_client.send, "POST", "/send_server_notice"
    )
    assert "/users" not in send_request.args[1]
    data = json.loads(send_request.kwargs["data"])
    assert data["content"]["body"] == TEXT_DATA
    check_requests_sent(mocked_matrix_client.send, "/send_server_notice")

    t.cancel()


@pytest.mark.asyncio
async def test_to_one_recipient_with_coordinator() -> None:
    mocked_matrix_client1, _, t1 = await create_fake_admin_bot(
        "example.org", validator=ConfirmValidator()
    )
    mocked_matrix_client1.send = mock_send_response()
    mocked_matrix_client2, _, t2 = await create_fake_admin_bot(
        "example2.org", is_coordinator=False, validator=ConfirmValidator()
    )
    mocked_matrix_client2.send = mock_send_response()
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

    # no call on coordinator
    check_requests_sent(mocked_matrix_client1.send)
    check_requests_sent(mocked_matrix_client1.client_session)

    # send the report a result
    mocked_matrix_client2.send_file_message.assert_awaited_once()
    mocked_matrix_client2.send_file_message.reset_mock()

    # one call to send notice for the executing bot
    check_requests_sent(mocked_matrix_client2.send, "/send_server_notice")
    check_requests_sent(mocked_matrix_client2.client_session)

    t1.cancel()
    t2.cancel()
