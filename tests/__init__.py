import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, NoReturn
from unittest.mock import AsyncMock

from matrix_bot.bot import MatrixBot
from nio import Event, MatrixRoom, RoomMessage

event_id_counter: int = 0


def generate_event_id(*args: Any, **kwargs: Any) -> str:
    global event_id_counter
    event_id_counter += 1
    return f"$eventid{event_id_counter}"


class MatrixClientMock:
    def __init__(self) -> None:
        self.user_id = "@admin:example.org"
        self.access_token = "AAAA"
        self.callbacks: dict[
            Callable[[MatrixRoom, Event], Awaitable[None] | None],
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

    def add_event_callback(
        self,
        callback: Callable[[MatrixRoom, Event], Awaitable[None] | None],
        filter: type[Event] | tuple[type[Event]] | None,
    ) -> None:
        self.callbacks[callback] = filter

    async def fake_synced_message(self, room: MatrixRoom, message: RoomMessage) -> None:
        for callback in self.callbacks:
            filter = self.callbacks[callback]
            if filter is None or isinstance(message, filter):
                await callback(room, message)

    async def sync_forever(*args: Any, **kwargs: Any) -> NoReturn:
        while True:
            await asyncio.sleep(0.001)


async def mock_client(bot: MatrixBot) -> MatrixClientMock:
    fake_client = MatrixClientMock()
    bot.matrix_client = fake_client
    bot.callbacks.matrix_client = fake_client
    return fake_client
