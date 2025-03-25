from collections.abc import Mapping
from typing import Any

import pytest
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.simple_command import SimpleCommand
from tests import USER1_ID, create_fake_command_bot


class SimpleTestCommand(SimpleCommand):
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

        super().__init__(room, message, matrix_client, extra_config)

    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return True


@pytest.mark.asyncio
async def test_success() -> None:
    mocked_client, t = await create_fake_command_bot([SimpleTestCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    mocked_client.check_sent_reactions("🚀", "✅")

    assert mocked_client.executed

    t.cancel()


class SimpleFailingTestCommand(SimpleTestCommand):
    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return False


@pytest.mark.asyncio
async def test_failure() -> None:
    mocked_client, t = await create_fake_command_bot([SimpleFailingTestCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    mocked_client.check_sent_reactions("🚀", "❌")

    assert mocked_client.executed

    t.cancel()
