import pytest
from nio import MatrixRoom
from typing_extensions import override

from matrix_command_bot.simple_commands import SimpleCommand
from tests import USER1_ID, create_fake_command_bot


class SuccessCommand(SimpleCommand):
    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return True


@pytest.mark.asyncio()
async def test_success() -> None:
    mocked_client, t = await create_fake_command_bot([SuccessCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    assert len(mocked_client.send_reaction.await_args_list) == 2
    assert mocked_client.send_reaction.await_args_list[0][0][2] == "🚀"
    assert mocked_client.send_reaction.await_args_list[1][0][2] == "✅"
    mocked_client.send_reaction.reset_mock()

    assert mocked_client.executed

    t.cancel()

class FailureCommand(SimpleCommand):
    @override
    async def simple_execute(self) -> bool:
        self.matrix_client.executed = True
        return False


@pytest.mark.asyncio()
async def test_failure() -> None:
    mocked_client, t = await create_fake_command_bot([FailureCommand])
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    assert len(mocked_client.send_reaction.await_args_list) == 2
    assert mocked_client.send_reaction.await_args_list[0][0][2] == "🚀"
    assert mocked_client.send_reaction.await_args_list[1][0][2] == "❌"
    mocked_client.send_reaction.reset_mock()

    assert mocked_client.executed

    t.cancel()
