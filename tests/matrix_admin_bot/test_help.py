import pytest
from nio import MatrixRoom

from matrix_admin_bot.adminbot import COMMANDS
from tests import USER1_ID, create_fake_admin_bot


@pytest.mark.asyncio
async def test_help_command() -> None:
    mocked_client, t = await create_fake_admin_bot()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!help")

    mocked_client.check_sent_message("Here are the available commands")

    for command in COMMANDS:
        await mocked_client.fake_synced_text_message(
            room,
            USER1_ID,
            f"!{command.KEYWORD} help",
        )
        mocked_client.check_sent_message(command.KEYWORD)  # pyright: ignore [reportUnknownArgumentType]

    t.cancel()
