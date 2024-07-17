from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

import matrix_command_bot
from matrix_admin_bot.commands.server_notice import ServerNoticeCommand
from matrix_command_bot.validation.validators.totp import TOTPValidator
from tests import USER1_ID, OkValidator, create_fake_command_bot, create_reply_relation, create_thread_relation


@pytest.mark.asyncio()
async def test_server_notice() -> None:
    matrix_command_bot.validation.SECURE_VALIDATOR = OkValidator
    mocked_client, t = await create_fake_command_bot([ServerNoticeCommand])
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    msg_event_id = await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!server_notice"
    )

    mocked_client.check_sent_message("Type your recipients with space separated")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "all",
        content=create_thread_relation(msg_event_id),
    )
    # mocked_client.check_sent_message("Type your notice")

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "Dear friends of Element",
        content={"body": "Dear **Friend**",
                 "format": "org.matrix.custom.html",
                 "formatted_body": "Dear <strong>Friend</strong>"}
                | create_thread_relation(msg_event_id),
    )

    mocked_client.check_sent_message("Dear friends of Element")

    await mocked_client.fake_synced_text_message(
        room,
        USER1_ID,
        "yes",
        content=create_thread_relation(msg_event_id),
    )

    # # one call to fetch the devices, and one call to reset the password
    # assert len(mocked_client.send.await_args_list) == 2
    # assert "/devices" in mocked_client.send.await_args_list[0][0][1]
    # assert "/reset_password/" in mocked_client.send.await_args_list[1][0][1]
    # mocked_client.send.reset_mock()

    t.cancel()


@pytest.mark.asyncio()
async def test_failed_server_notice() -> None:
    # matrix_command_bot.validation.SECURE_VALIDATOR = OkValidator()
    # mocked_client, t = await create_fake_command_bot([ServerNoticeCommand])
    # mocked_client.send = AsyncMock(
    #     return_value=Mock(ok=False, json=AsyncMock(return_value={}))
    # )
    #
    # room = MatrixRoom("!roomid:example.org", USER1_ID)
    #
    # await mocked_client.fake_synced_text_message(
    #     room, USER1_ID, "!reset_password @user_to_reset:example.org"
    # )
    #
    # mocked_client.check_sent_message("Couldn't reset the password")

    # t.cancel()
    pass
