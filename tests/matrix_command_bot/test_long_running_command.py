import asyncio
from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from matrix_command_bot.simple_command import SimpleCommand
from nio import MatrixRoom, RoomMessage
import pytest
import structlog
from tests import USER1_ID, create_fake_command_bot
from typing_extensions import override

logger = structlog.get_logger(__name__)

class KeywordCommand(SimpleCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        keyword: str,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.keyword = keyword

        MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        ).command(keyword)


class SuccessCommand(KeywordCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, "success", extra_config)

    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.success_executed = True
        return True

class LongRunningCommand(KeywordCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, "long", extra_config)


    @override
    async def simple_execute(self) -> bool:
        while True:
            await asyncio.sleep(1)

@pytest.mark.asyncio
async def test_long_running_command() -> None:
    mocked_client, t = await create_fake_command_bot([SuccessCommand, LongRunningCommand])
    mocked_client.success_executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!long", wait_for_commands_execution=False)
    await mocked_client.fake_synced_text_message(room, USER1_ID, "!success", wait_for_commands_execution=False)

    # We can't wait for the command tasks to finish here, because the long running command will not finish
    # So we just wait a bit for the success command to be executed
    await asyncio.sleep(0.1)

    assert mocked_client.success_executed

    t.cancel()
