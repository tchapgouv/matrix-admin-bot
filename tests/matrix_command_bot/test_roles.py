import pytest
from nio import MatrixRoom

from matrix_command_bot.commandbot import Role
from tests import (
    USER1_ID,
    USER2_ID,
    USER3_ID,
    create_fake_command_bot,
    create_thread_relation,
)
from tests.matrix_command_bot.test_simple_command import SimpleTestCommand
from tests.matrix_command_bot.validation.validators.test_confirm import (
    ConfirmValidatedCommand,
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
    authorized_user_id = USER1_ID
    unauthorized_user_id = USER2_ID
    roles = {
        authorized_user_id: [
            Role(
                name="authorized_user",
                all_commands=False,
                allowed_commands=[SimpleTestCommand],
            )
        ],
    }
    mocked_client, t = await create_fake_command_bot([SimpleTestCommand], roles=roles)
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", authorized_user_id)

    await mocked_client.fake_synced_text_message(room, unauthorized_user_id, "!test")

    assert not mocked_client.executed
    mocked_client.executed = False

    await mocked_client.fake_synced_text_message(room, authorized_user_id, "!test")

    assert mocked_client.executed
    mocked_client.executed = False

    t.cancel()


@pytest.mark.asyncio
async def test_normal_role_with_interaction() -> None:
    authorized_user_id = USER1_ID
    unauthorized_user_id = USER2_ID
    roles = {
        authorized_user_id: [
            Role(
                name="authorized_user",
                all_commands=False,
                allowed_commands=[ConfirmValidatedCommand],
            )
        ],
    }
    mocked_client, t = await create_fake_command_bot(
        [ConfirmValidatedCommand], roles=roles
    )
    mocked_client.executed = False

    room = MatrixRoom("!roomid:example.org", authorized_user_id)

    command_event_id = await mocked_client.fake_synced_text_message(
        room, authorized_user_id, "!test"
    )

    await mocked_client.fake_synced_text_message(
        room,
        unauthorized_user_id,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert not mocked_client.executed
    mocked_client.executed = False

    await mocked_client.fake_synced_text_message(
        room,
        authorized_user_id,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert mocked_client.executed

    t.cancel()


@pytest.mark.asyncio
async def test_other_users_interaction_role() -> None:
    bot_id = USER1_ID
    authorized_user_id = USER2_ID
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

    await mocked_client.fake_synced_text_message(
        room,
        unauthorized_user_id,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert not mocked_client.executed
    mocked_client.executed = False

    await mocked_client.fake_synced_text_message(
        room,
        authorized_user_id,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert mocked_client.executed

    t.cancel()
