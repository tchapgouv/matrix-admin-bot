import pytest
from nio import MatrixRoom
from typing_extensions import override

from matrix_command_bot.commandbot import CommandBot
from matrix_command_bot.simple_commands import SimpleCommand
from tests import USER1_ID, mock_client_and_run


class ConfirmCommand(SimpleCommand):
    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return True


@pytest.mark.asyncio()
async def test_simple_command() -> None:
    bot = CommandBot(
        homeserver="http://localhost:8008",
        username="",
        password="",
        commands=[ConfirmCommand],
        coordinator=None,
    )
    mocked_client, t = await mock_client_and_run(bot)
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    assert len(mocked_client.send_reaction.await_args_list) == 2
    assert mocked_client.send_reaction.await_args_list[0][0][2] == "🚀"
    assert mocked_client.send_reaction.await_args_list[1][0][2] == "✅"
    mocked_client.send_reaction.reset_mock()

    assert mocked_client.executed

    t.cancel()
