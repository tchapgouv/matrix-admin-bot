import pytest
from nio import MatrixRoom

from matrix_command_bot.commandbot import Role
from tests import USER1_ID, USER2_ID, create_fake_command_bot
from tests.matrix_command_bot.test_simple_command import (
    SimpleFailingTestCommand,
    SimpleTestCommand,
)


@pytest.mark.asyncio
async def test_admin_role() -> None:
    roles = {USER1_ID: [Role(name="admin", all_commands=True)]}
    mocked_client, t = await create_fake_command_bot([SimpleTestCommand], roles=roles)
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    assert mocked_client.executed

    mocked_client.executed = False

    await mocked_client.fake_synced_text_message(room, USER2_ID, "!test")

    assert not mocked_client.executed

    t.cancel()


@pytest.mark.asyncio
async def test_normal_role() -> None:
    roles = {
        USER1_ID: [
            Role(name="user1", all_commands=False, allowed_commands=[SimpleTestCommand])
        ],
    }
    mocked_client, t = await create_fake_command_bot([SimpleTestCommand], roles=roles)
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(room, USER1_ID, "!test")

    assert mocked_client.executed
    mocked_client.executed = False

    await mocked_client.fake_synced_text_message(room, USER2_ID, "!test")

    assert not mocked_client.executed
    mocked_client.executed = False

    roles[USER2_ID] = [
        Role(
            name="user2",
            all_commands=False,
            allowed_commands=[SimpleFailingTestCommand],
        )
    ]

    await mocked_client.fake_synced_text_message(room, USER2_ID, "!test")

    assert not mocked_client.executed
    mocked_client.executed = False

    roles[USER2_ID] = [
        Role(name="user2", all_commands=False, allowed_commands=[SimpleTestCommand])
    ]

    await mocked_client.fake_synced_text_message(room, USER2_ID, "!test")

    assert mocked_client.executed
    mocked_client.executed = False

    t.cancel()
