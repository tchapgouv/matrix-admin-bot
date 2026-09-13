import asyncio
from collections.abc import Mapping
from typing import Any, override

import pytest
import structlog
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage

from matrix_command_bot.validation.simple_command import SimpleValidatedCommand
from matrix_command_bot.validation.validators.confirm import ConfirmValidator
from tests import (
    USER1_ID,
    OkValidator,
    create_fake_command_bot,
    create_thread_relation,
    timeout,
)

logger = structlog.get_logger(__name__)


class KeywordCommand(SimpleValidatedCommand):
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
@timeout(2)
async def test_command_concurrency() -> None:
    mocked_client, t = await create_fake_command_bot(
        [SuccessCommand, LongRunningCommand], validator=OkValidator()
    )
    mocked_client.success_executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!long", wait_for_commands_execution=False
    )
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!success", wait_for_commands_execution=False
    )

    # We can't wait for the command tasks to finish here,
    # because the long running command will not finish
    # so we just wait a bit for the success command to be executed
    await asyncio.sleep(0.1)

    assert mocked_client.success_executed

    t.cancel()


@pytest.mark.asyncio
@timeout(2)
async def test_command_with_confirm_concurrency() -> None:
    mocked_client, t = await create_fake_command_bot(
        [SuccessCommand, LongRunningCommand], validator=ConfirmValidator()
    )
    mocked_client.success_executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    long_cmd_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!long"
    )
    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(long_cmd_event_id),
        wait_for_commands_execution=False,
    )
    success_cmd_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!success", wait_for_commands_execution=False
    )
    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(success_cmd_event_id),
        wait_for_commands_execution=False,
    )

    # We can't wait for the command tasks to finish here,
    # because the long running command will not finish
    # so we just wait a bit for the success command to be executed
    await asyncio.sleep(0.1)

    assert mocked_client.success_executed

    t.cancel()


class LongShouldExecuteCommand(KeywordCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(
            room, message, matrix_client, "long_should_execute", extra_config
        )

    async def should_execute(self) -> bool:
        await asyncio.sleep(1)
        return True

    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.success_executed = True
        return True


@pytest.mark.asyncio
@timeout(3)
async def test_reply_received_during_execution() -> None:
    mocked_client, t = await create_fake_command_bot(
        [LongShouldExecuteCommand], validator=ConfirmValidator()
    )

    mocked_client.success_executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    long_cmd_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!long_should_execute", wait_for_commands_execution=False
    )
    # Confirm the command right away while it's still in should_execute.
    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(long_cmd_event_id),
        wait_for_commands_execution=False,
    )
    await asyncio.sleep(0.1)

    # The command should not have been executed yet since it's still in should_execute.
    assert not mocked_client.success_executed

    await asyncio.sleep(1)

    # The command should have been executed now that should_execute has returned.
    assert mocked_client.success_executed

    t.cancel()
