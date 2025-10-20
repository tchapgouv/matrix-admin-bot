import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
import structlog
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.validation import IValidator
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
        secure_validator: IValidator = extra_config.get("secure_validator")  # pyright: ignore[reportAssignmentType]
        super().__init__(room, message, matrix_client, secure_validator, extra_config)
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
        [SuccessCommand, LongRunningCommand], secure_validator=OkValidator()
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
        [SuccessCommand, LongRunningCommand], secure_validator=ConfirmValidator()
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
