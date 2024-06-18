import asyncio
import time
from asyncio import Task
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, NoReturn
from unittest.mock import AsyncMock

from matrix_bot.bot import MatrixBot
from nio import Event, MatrixRoom, RoomMessage, RoomMessageText
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.commandbot import CommandBot
from matrix_command_bot.validation import IValidator

USER1_ID = "@user1:example.org"

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
        *,
        content: Mapping[str, Any] | None = None,
    ) -> str:
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
            format=None,
            formatted_body=None,
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


async def create_fake_command_bot(
    commands: list[type[ICommand]],
) -> tuple[MatrixClientMock, Task[None]]:
    bot = CommandBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=commands,
        coordinator=None,
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


def create_thread_relation(thread_root: str) -> Mapping[str, Any]:
    return {
        "m.relates_to": {
            "event_id": thread_root,
            "rel_type": "m.thread",
        }
    }


class OkValidator(IValidator):
    @override
    async def validate(
        self,
        user_response: RoomMessage | None,
        command: ICommand,
    ) -> bool:
        return True
