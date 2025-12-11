import datetime
from typing import Any

import pyotp
import pytest
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.commandbot import Role
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand
from matrix_command_bot.validation.validators.totp import TOTPValidator
from tests import (
    USER1_ID,
    USER2_ID,
    USER3_ID,
    create_fake_command_bot,
    create_thread_relation,
)

TOTP_SEED = "P7ZBD5ZLMACOOTX4"


class ConfirmValidatedCommand(SimpleValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: dict[str, Any],
    ) -> None:
        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        event_parser.command("test")

        extra_config["validator"] = TOTPValidator({USER1_ID: TOTP_SEED})

        super().__init__(
            room,
            message,
            matrix_client,
            extra_config,
        )

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

    mocked_client.check_sent_reactions("🔢")
    mocked_client.check_sent_message("authentication code")

    code = pyotp.TOTP(TOTP_SEED).now()
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, code, extra_content=create_thread_relation(command_event_id)
    )

    assert mocked_client.executed

    t.cancel()


@pytest.mark.asyncio
async def test_failures() -> None:
    mocked_client, t = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid1:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )

    mocked_client.send_text_message.reset_mock()

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "yes", extra_content=create_thread_relation(command_event_id)
    )

    mocked_client.check_sent_message("parse")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "000000", extra_content=create_thread_relation(command_event_id)
    )

    mocked_client.check_sent_message("Wrong authentication code")

    assert not mocked_client.executed

    t.cancel()


@pytest.mark.asyncio
async def test_totp_window() -> None:
    mocked_client, t = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!test"
    )

    code = pyotp.TOTP(TOTP_SEED).at(datetime.datetime.now(), counter_offset=-2)
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, code, extra_content=create_thread_relation(command_event_id)
    )

    assert not mocked_client.executed

    code = pyotp.TOTP(TOTP_SEED).at(datetime.datetime.now(), counter_offset=2)
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, code, extra_content=create_thread_relation(command_event_id)
    )

    assert not mocked_client.executed

    code = pyotp.TOTP(TOTP_SEED).at(datetime.datetime.now(), counter_offset=1)
    await mocked_client.fake_synced_text_message(
        room, USER1_ID, code, extra_content=create_thread_relation(command_event_id)
    )

    assert mocked_client.executed

    t.cancel()


@pytest.mark.asyncio
async def test_with_allow_other_users_interaction_role() -> None:
    bot_id = USER2_ID
    authorized_user_id = USER1_ID
    unauthorized_user_id = USER3_ID

    roles = {
        bot_id: [
            Role(
                name="bot",
                all_commands=False,
                allowed_commands=[ConfirmValidatedCommand],
                allow_other_users_interaction=True,
            )
        ],
        authorized_user_id: [
            Role(
                name="user",
                all_commands=False,
                allowed_commands=[ConfirmValidatedCommand],
            )
        ],
    }

    mocked_client, t = await create_fake_command_bot(
        [ConfirmValidatedCommand], roles=roles
    )
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", bot_id)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, bot_id, "!test"
    )

    code = pyotp.TOTP(TOTP_SEED).now()
    await mocked_client.fake_synced_text_message(
        room,
        unauthorized_user_id,
        code,
        extra_content=create_thread_relation(command_event_id),
    )

    assert not mocked_client.executed
    mocked_client.executed = False

    code = pyotp.TOTP(TOTP_SEED).now()
    await mocked_client.fake_synced_text_message(
        room,
        authorized_user_id,
        code,
        extra_content=create_thread_relation(command_event_id),
    )

    assert mocked_client.executed

    t.cancel()
