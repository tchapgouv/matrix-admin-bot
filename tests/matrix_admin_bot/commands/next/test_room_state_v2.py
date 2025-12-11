from unittest.mock import AsyncMock, Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    create_fake_admin_bot_with_mas_enabled,
)


@pytest.mark.asyncio
async def test_room_state(monkeypatch: MonkeyPatch) -> None:
    (
        mocked_matrix_client,
        _,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(
        monkeypatch, validator=OkValidator()
    )
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!room_state !theroomid:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert (
        "/rooms/!theroomid:example.org/state"
        in mocked_matrix_client.send.await_args_list[0][0][1]
    )
    mocked_matrix_client.send.reset_mock()

    t.cancel()
