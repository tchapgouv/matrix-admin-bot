from unittest.mock import AsyncMock, Mock

import pytest
from nio import MatrixRoom

from tests import USER1_ID, OkValidator, create_fake_admin_bot


@pytest.mark.asyncio
async def test_room_details() -> None:
    mocked_client, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!room_details !theroomid:example.org"
    )

    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()

    assert len(mocked_client.send.await_args_list) == 1
    assert (
        "/rooms/!theroomid:example.org" in mocked_client.send.await_args_list[0][0][1]
    )
    mocked_client.send.reset_mock()

    t.cancel()
