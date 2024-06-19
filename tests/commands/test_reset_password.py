import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom, RoomMessage, RoomMessageText

from matrix_admin_bot.adminbot import COMMANDS
from matrix_admin_bot.validatebot import ValidateBot
from matrix_admin_bot.validators.confirm import ConfirmValidator

event_id_counter: int = 0


def generate_event_id() -> str:
    global event_id_counter
    event_id_counter += 1
    return f"$eventid{event_id_counter}"


class MatrixClientMock:
    def __init__(self) -> None:
        self.user_id = "@admin:example.org"
        self.access_token = "AAAA"
        self.callbacks = {}

        self.automatic_login = AsyncMock()
        self.sync = AsyncMock()
        self.send = AsyncMock(
            return_value=Mock(ok=True, json=AsyncMock(return_value={}))
        )
        self.send_markdown_message = AsyncMock(return_value=generate_event_id())
        self.send_reaction = AsyncMock(return_value=generate_event_id())
        self.send_file_message = AsyncMock(return_value=generate_event_id())
        self.room_redact = AsyncMock()

    def add_event_callback(self, callback, filter):
        self.callbacks[callback] = filter

    async def fake_synced_message(self, room: MatrixRoom, message: RoomMessage):
        for callback in self.callbacks:
            filter = self.callbacks[callback]
            if filter is None or isinstance(message, filter):
                await callback(room, message)

    async def sync_forever(*args, **kwargs):
        while True:
            await asyncio.sleep(0.001)


@pytest.mark.asyncio()
async def test_reset_password() -> None:
    fake_client = MatrixClientMock()
    bot = ValidateBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=COMMANDS,
        secure_validator=ConfirmValidator(),
        coordinator=None,
    )
    bot.matrix_client = fake_client
    bot.callbacks.matrix_client = fake_client
    t = asyncio.create_task(bot.main())

    await asyncio.sleep(0.01)

    room = MatrixRoom("!roomid:example.org", "@user1:example.org")

    command_event_id = generate_event_id()
    await fake_client.fake_synced_message(
        room,
        RoomMessageText(
            source={
                "event_id": command_event_id,
                "sender": "@user1:example.org",
                "origin_server_ts": 1900,
            },
            body="!reset_password @user_to_reset:example.org",
            format=None,
            formatted_body=None,
        ),
    )

    fake_client.send_markdown_message.assert_awaited_once()
    assert (
        "You are about to reset password of the following users"
        in fake_client.send_markdown_message.await_args[0][1]
    )
    fake_client.send_markdown_message.reset_mock()

    await fake_client.fake_synced_message(
        room,
        RoomMessageText(
            source={
                "event_id": generate_event_id(),
                "sender": "@user1:example.org",
                "origin_server_ts": 19001,
                "content": {
                    "m.relates_to": {
                        "event_id": command_event_id,
                        "rel_type": "m.thread",
                    }
                },
            },
            body="yes",
            format=None,
            formatted_body=None,
        ),
    )

    fake_client.send_file_message.assert_awaited_once()
    fake_client.send_file_message.reset_mock()

    # one call to fetch the devices, and one call to reset the password
    assert len(fake_client.send.await_args_list) == 2
    fake_client.send.reset_mock()

    t.cancel()
