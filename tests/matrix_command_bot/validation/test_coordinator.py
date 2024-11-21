import pytest
from nio import MatrixRoom

from tests import (
    USER1_ID,
    create_fake_command_bot,
    create_thread_relation,
    fake_synced_text_message,
)
from tests.matrix_command_bot.validation.validators.test_confirm import (
    ConfirmValidatedCommand,
)


@pytest.mark.asyncio
async def test_with_single_coordinator() -> None:
    mocked_client1, t1 = await create_fake_command_bot([ConfirmValidatedCommand])
    mocked_client1.executed = False
    mocked_client2, t2 = await create_fake_command_bot(
        [ConfirmValidatedCommand], is_coordinator=False
    )
    mocked_client2.executed = False
    # the third bot instance is not concerned by the command and should not execute
    # nor send reactions
    mocked_client3, t3 = await create_fake_command_bot(
        [ConfirmValidatedCommand], is_coordinator=False, should_execute=False
    )
    mocked_client3.executed = False

    mocked_clients = [mocked_client1, mocked_client2, mocked_client3]

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await fake_synced_text_message(
        mocked_clients, room, USER1_ID, "!test"
    )

    mocked_client1.check_sent_message("yes")
    mocked_client2.check_no_sent_message()

    await fake_synced_text_message(
        mocked_clients,
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert mocked_client1.executed
    assert mocked_client2.executed
    assert not mocked_client3.executed

    mocked_client1.check_sent_reactions("✏️", "🚀", "✅")
    mocked_client2.check_sent_reactions("🚀", "✅")
    mocked_client3.check_sent_reactions()

    t1.cancel()
    t2.cancel()
    t3.cancel()


@pytest.mark.asyncio
async def test_with_non_executing_coordinator() -> None:
    mocked_client1, t1 = await create_fake_command_bot(
        [ConfirmValidatedCommand], should_execute=False
    )
    mocked_client1.executed = False
    mocked_client2, t2 = await create_fake_command_bot(
        [ConfirmValidatedCommand], is_coordinator=False
    )
    mocked_client2.executed = False

    mocked_clients = [mocked_client1, mocked_client2]

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    command_event_id = await fake_synced_text_message(
        mocked_clients, room, USER1_ID, "!test"
    )

    mocked_client1.check_sent_message("yes")
    mocked_client2.check_no_sent_message()

    await fake_synced_text_message(
        mocked_clients,
        room,
        USER1_ID,
        "yes",
        extra_content=create_thread_relation(command_event_id),
    )

    assert not mocked_client1.executed
    assert mocked_client2.executed

    mocked_client1.check_sent_reactions("✏️")
    assert len(mocked_client1.room_redact.await_args_list) == 1
    mocked_client2.check_sent_reactions("🚀", "✅")

    t1.cancel()
    t2.cancel()
