from collections.abc import Mapping
from typing import Any

import pytest
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.validation.simple_command import SimpleValidatedCommand
from matrix_command_bot.validation.validators.confirm import ConfirmValidator
from tests import (
    USER1_ID,
    USER2_ID,
    create_fake_command_bot,
    create_reply_relation,
    create_thread_relation,
)


class ConfirmValidatedCommand(SimpleValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        event_parser.command("test")

        self._should_execute = extra_config.get("should_execute", True)
        super().__init__(room, message, matrix_client, ConfirmValidator(), extra_config)

    @override
    async def should_execute(self) -> bool:
        return self._should_execute

    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return True


@pytest.mark.asyncio
async def test_success() -> None:
    mocked_client, t = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )
    mocked_client.check_sent_reactions("✏️")
    mocked_client.check_sent_message("yes")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "> fallback reply\n\nyes",
        extra_content=create_reply_relation(command_event_id),
    )
    assert mocked_client.executed

    t.cancel()


@pytest.mark.asyncio
async def test_failures_then_success() -> None:
    mocked_client, t = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "no", extra_content=create_thread_relation(command_event_id)
    )

    assert not mocked_client.executed

    await mocked_client.fake_synced_text_message(
        room,
        USER2_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert mocked_client.executed

    t.cancel()
