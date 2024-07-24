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


@pytest.mark.asyncio()
async def test_with_single_coordinator() -> None:
    mocked_client1, t1 = await create_fake_command_bot([ConfirmValidatedCommand])
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

    assert mocked_client1.executed
    assert mocked_client2.executed

    t1.cancel()
    t2.cancel()
