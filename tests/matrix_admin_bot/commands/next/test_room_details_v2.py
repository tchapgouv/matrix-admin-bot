import pytest
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import mock_send_response


@pytest.mark.asyncio
async def test_room_details() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!room_details !theroomid:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    check_requests_sent(mocked_matrix_client.send, "/rooms/!theroomid:example.org")

    t.cancel()
