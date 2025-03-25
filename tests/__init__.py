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

from matrix_admin_bot.adminbot import AdminBot, AdminBotConfig
from matrix_command_bot.command import ICommand
from matrix_command_bot.commandbot import CommandBot, Role
from matrix_command_bot.validation import IValidator
from tchap_admin_bot.tchapadminbot import TchapAdminBot, TchapAdminBotConfig

USER1_ID = "@user1:example.org"
USER2_ID = "@user2:example.org"
USER3_ID = "@user3:example.org"
USER4_ID = "@user4:example.org"

event_id_counter: int = 0


def generate_event_id(*_args: Any, **_kwargs: Any) -> str:
    global event_id_counter
    event_id_counter += 1
    return f"$eventid{event_id_counter}"


class SendMock(AsyncMock):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.last_handled_await_args_index = 0

    def new_await_args_list(self):  # noqa: ANN201
        current_index = self.last_handled_await_args_index
        self.last_handled_await_args_index = len(self.await_args_list)
        return self.await_args_list[current_index:]


class MatrixClientMock:
    def __init__(self, server_name: str = "example.org") -> None:
        self.user_id = f"@admin:{server_name}"
        self.access_token = "AAAA"
        self.callbacks: dict[
            Callable[[MatrixRoom, Event], Awaitable[None]],
            type[Event] | tuple[type[Event]] | None,
        ] = {}

        self.automatic_login = AsyncMock()
        self.sync = AsyncMock()
        self.send_text_message = SendMock(side_effect=generate_event_id)
        self.send_markdown_message = SendMock(side_effect=generate_event_id)
        self.send_html_message = SendMock(side_effect=generate_event_id)
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

    async def fake_synced_message(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        *,
        wait_for_commands_execution: bool = True,
    ) -> None:
        for callback in self.callbacks:
            event_filter = self.callbacks[callback]
            if event_filter is None or isinstance(message, event_filter):
                await callback(room, message)

        if wait_for_commands_execution:
            await wait_for_command_tasks()

        # Inject events produced by the bot into the bot loop
        # This is useful to test the bot's reaction to its own events, including
        # potential infinite loops
        for send_mock in self.send_text_message_mocks:
            for args in send_mock.new_await_args_list():
                # TODO: deal with extra_content for thread and reply relation,
                # also we should use formatted_body for html and markdown messages
                await self.fake_synced_text_message(
                    room,
                    sender=self.user_id,
                    text=args[0][1],
                )

        if wait_for_commands_execution:
            await wait_for_command_tasks()

    async def fake_synced_text_message(
        self,
        room: MatrixRoom,
        sender: str,
        text: str,
        format_: str | None = None,
        formatted_body: str | None = None,
        *,
        extra_content: Mapping[str, Any] | None = None,
        event_id: str | None = None,
        wait_for_commands_execution: bool = True,
    ) -> str:
        if not event_id:
            event_id = generate_event_id()
        if extra_content is None:
            extra_content = {}
        source: dict[str, Any] = {
            "event_id": event_id,
            "sender": sender,
            "origin_server_ts": int(time.time() * 1000),
            "type": "m.room.message",
            "content": {
                "msgtype": "m.text",
                "body": text,
                **extra_content,
            },
        }
        if format_ and formatted_body:
            source["content"]["format"] = format_
            source["content"]["formatted_body"] = formatted_body
        message = RoomMessageText.parse_event(source)
        assert isinstance(message, RoomMessageText)
        await self.fake_synced_message(
            room, message, wait_for_commands_execution=wait_for_commands_execution
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

    def check_redactions(self, expected_redactions: int) -> None:
        assert len(self.room_redact.await_args_list) == expected_redactions
        self.room_redact.reset_mock()

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
    extra_content: Mapping[str, Any] | None = None,
) -> str:
    event_id = generate_event_id()
    for mocked_client in mocked_clients:
        await mocked_client.fake_synced_text_message(
            room, sender, text, extra_content=extra_content, event_id=event_id
        )
    return event_id


async def create_fake_command_bot(
    commands: list[type[ICommand]],
    server_name: str = "example.org",
    roles: dict[str, list[Role]] | None = None,
    **extra_config: Any,
) -> tuple[MatrixClientMock, Task[None]]:
    bot = CommandBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=commands,
        roles=roles,
        **extra_config,
    )
    return await mock_client_and_run(bot, server_name)


async def create_fake_admin_bot(
    server_name: str = "example.org",
    *,
    is_coordinator: bool = True,
    **extra_config: Any,
) -> tuple[MatrixClientMock, Task[None]]:
    bot = AdminBot(
        AdminBotConfig(
            homeserver="http://localhost:8008",
            bot_username="",
            bot_password="",
            is_coordinator=is_coordinator,
            allowed_room_ids=[],
            totps={},
        ),
        **extra_config,
    )
    return await mock_client_and_run(bot, server_name)


async def create_fake_tchap_admin_bot(
    server_name: str = "example.org",
    *,
    is_coordinator: bool = True,
    **extra_config: Any,
) -> tuple[MatrixClientMock, Task[None]]:
    bot = TchapAdminBot(
        TchapAdminBotConfig(
            homeserver="http://localhost:8008",
            identity_server="http://localhost:8090",
            bot_username="",
            bot_password="",
            is_coordinator=is_coordinator,
            allowed_room_ids=[],
            totps={},
        ),
        **extra_config,
    )
    return await mock_client_and_run(bot, server_name)


async def mock_client_and_run(
    bot: MatrixBot, server_name: str = "example.org"
) -> tuple[MatrixClientMock, Task[None]]:
    fake_client = MatrixClientMock(server_name)
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


async def wait_for_command_tasks() -> None:
    # Run all pending command tasks in the event loop except current one
    await asyncio.gather(
        *[
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and not task.done()
            and task.get_name().startswith("ExecuteCommand-")
        ],
        return_exceptions=True,
    )
    # Let the event loop process one more cycle
    await asyncio.sleep(0)
