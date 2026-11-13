import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from matrix_command_bot.util import send_report

ROOM_ID = "!roomid:example.org"
REPLIED_EVENT_ID = "$eventid1"


def make_mocked_client() -> Mock:
    client = Mock()
    client.send_html_message = AsyncMock()
    client.send_file_message = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_send_report_as_html_message_when_small() -> None:
    mocked_client = make_mocked_client()
    report: dict[str, Any] = {"command": "lock", "users": {}}

    await send_report(report, "lock", mocked_client, ROOM_ID, REPLIED_EVENT_ID)

    mocked_client.send_html_message.assert_awaited_once()
    assert mocked_client.send_file_message.await_count == 0
    args = mocked_client.send_html_message.await_args
    assert args is not None
    assert args.args[0] == ROOM_ID
    json_str = json.dumps(report, indent=2, sort_keys=True)
    assert args.args[1] == f"<pre><code>{json_str}</code></pre>\n"
    assert args.kwargs["reply_to"] == REPLIED_EVENT_ID
    assert args.kwargs["thread_root"] == REPLIED_EVENT_ID


@pytest.mark.asyncio
async def test_send_report_as_file_when_big() -> None:
    mocked_client = make_mocked_client()
    report: dict[str, Any] = {"command": "server_notice", "data": "a" * 30000}

    await send_report(report, "notice", mocked_client, ROOM_ID, REPLIED_EVENT_ID)

    mocked_client.send_file_message.assert_awaited_once()
    assert mocked_client.send_html_message.await_count == 0
    args = mocked_client.send_file_message.await_args
    assert args is not None
    assert args.args[0] == ROOM_ID
    assert args.kwargs["mime_type"] == "application/json"
    assert args.kwargs["filename"].endswith("-notice.json")
    assert args.kwargs["reply_to"] == REPLIED_EVENT_ID
    assert args.kwargs["thread_root"] == REPLIED_EVENT_ID
