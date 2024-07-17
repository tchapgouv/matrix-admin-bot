import asyncio
import time
from asyncio import Task
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, NoReturn
from unittest.mock import AsyncMock

import pytest
from matrix_bot.bot import MatrixBot
from nio import Event, MatrixRoom, RoomMessage, RoomMessageText
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.commandbot import CommandBot
from matrix_command_bot.validation import IValidator

USER1_ID = "@user1:example.org"
USER2_ID = "@user2:example.org"
USER3_ID = "@user3:example.org"
USER4_ID = "@user4:example.org"

event_id_counter: int = 0


def generate_event_id(*_args: Any, **_kwargs: Any) -> str:
    global event_id_counter
    event_id_counter += 1
    return f"$eventid{event_id_counter}"


class MatrixClientMock:
    def __init__(self) -> None:
        self.user_id = "@admin:example.org"
        self.access_token = "AAAA"
        self.callbacks: dict[
            Callable[[MatrixRoom, Event], Awaitable[None]],
            type[Event] | tuple[type[Event]] | None,
        ] = {}

        self.automatic_login = AsyncMock()
        self.sync = AsyncMock()
        self.send_text_message = AsyncMock(side_effect=generate_event_id)
        self.send_markdown_message = AsyncMock(side_effect=generate_event_id)
        self.send_html_message = AsyncMock(side_effect=generate_event_id)
        self.send_image_message = AsyncMock(side_effect=generate_event_id)
        self.send_video_message = AsyncMock(side_effect=generate_event_id)
        self.send_file_message = AsyncMock(side_effect=generate_event_id)
        self.send_reaction = AsyncMock(side_effect=generate_event_id)
        self.room_redact = AsyncMock()
        self.sync_forever_called = False

        self.send_text_message_mocks = [
            self.send_text_message,
            self.send_markdown_message,
            self.send_html_message,
        ]

    def add_event_callback(
        self,
        callback: Callable[[MatrixRoom, Event], Awaitable[None]],
        event_filter: type[Event] | tuple[type[Event]] | None,
    ) -> None:
        self.callbacks[callback] = event_filter

    async def fake_synced_message(self, room: MatrixRoom, message: RoomMessage) -> None:
        for callback in self.callbacks:
            event_filter = self.callbacks[callback]
            if event_filter is None or isinstance(message, event_filter):
                await callback(room, message)

    async def fake_synced_text_message(
        self,
        room: MatrixRoom,
        sender: str,
        text: str,
        format_: str | None = None,
        formatted_body: str | None = None,
        *,
        content: Mapping[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str:
        if not event_id:
            event_id = generate_event_id()
        source: dict[str, Any] = {
            "event_id": event_id,
            "sender": sender,
            "origin_server_ts": int(time.time() * 1000),
        }
        if content:
            source["content"] = content
        message = RoomMessageText(
            source=source,
            body=text,
            format=format_,
            formatted_body=formatted_body,
        )
        await self.fake_synced_message(
            room,
            message,
        )
        return event_id

    async def sync_forever(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        self.sync_forever_called = True
        while True:
            await asyncio.sleep(30)

    def check_sent_reactions(self, *expected_reactions: str) -> None:
        assert len(self.send_reaction.await_args_list) == len(expected_reactions)
        for i in range(len(expected_reactions)):
            assert self.send_reaction.await_args_list[i][0][2] == expected_reactions[i]
        self.send_reaction.reset_mock()

    def check_no_sent_message(self) -> None:
        for send_mock in self.send_text_message_mocks:
            assert send_mock.await_count == 0

    def check_sent_message(self, contains: str) -> None:
        for send_mock in self.send_text_message_mocks:
            if send_mock.await_count > 0:
                msg = send_mock.await_args_list[0][0][1]
                if contains in msg:
                    send_mock.reset_mock()
                    return
        pytest.fail("No matching sent message")


async def fake_synced_text_message(
    mocked_clients: list[MatrixClientMock],
    room: MatrixRoom,
    sender: str,
    text: str,
    *,
    content: Mapping[str, Any] | None = None,
) -> str:
    event_id = generate_event_id()
    for mocked_client in mocked_clients:
        await mocked_client.fake_synced_text_message(
            room, sender, text, content=content, event_id=event_id
        )
    return event_id


async def create_fake_command_bot(
    commands: list[type[ICommand]],
    **extra_config: Any,
) -> tuple[MatrixClientMock, Task[None]]:
    bot = CommandBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=commands,
        **extra_config,
    )
    return await mock_client_and_run(bot)


async def mock_client_and_run(bot: MatrixBot) -> tuple[MatrixClientMock, Task[None]]:
    fake_client = MatrixClientMock()
    bot.matrix_client = fake_client
    bot.callbacks.matrix_client = fake_client

    t = asyncio.create_task(bot.main())
    while not fake_client.sync_forever_called:
        await asyncio.sleep(0.001)

    return fake_client, t


def create_thread_relation(thread_root_id: str) -> Mapping[str, Any]:
    return {
        "m.relates_to": {
            "event_id": thread_root_id,
            "rel_type": "m.thread",
        }
    }


def create_replace_relation(original_event_id: str) -> Mapping[str, Any]:
    return {
        "m.relates_to": {
            "event_id": original_event_id,
            "rel_type": "m.replace",
        }
    }


def create_reply_relation(replied_event_id: str) -> Mapping[str, Any]:
    return {"m.relates_to": {"m.in_reply_to": {"event_id": replied_event_id}}}


class OkValidator(IValidator):
    @override
    async def validate(
        self,
        user_response: RoomMessage | None,
        command: ICommand,
    ) -> bool:
        return True
