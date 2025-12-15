from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import InteractiveValidatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.util import get_server_name


class RoomDetailsCommandV2(InteractiveValidatedCommand):
    KEYWORD = "room_details"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]

        self.failed_room_ids: list[str] = []

    async def room_details(self, room_id: str) -> bool:
        if get_server_name(room_id) != self.server_name:
            return True

        resp = await self.admin_client.send_to_synapse(
            "GET", f"/_synapse/admin/v1/rooms/{room_id}"
        )

        self.json_report.setdefault(room_id, {})

        if resp.ok:
            json_body = await resp.json()
            self.json_report[room_id] = json_body
        else:
            json_body = await resp.json()
            self.json_report[room_id].update(json_body)
            self.failed_room_ids.append(room_id)
            return False

        return True

    @override
    async def should_execute(self) -> bool:
        self.room_ids = self.command_text.split()

        return any(
            get_server_name(room_id) == self.server_name for room_id in self.room_ids
        )

    @override
    async def simple_execute(self) -> bool:
        for room_id in self.room_ids:
            await self.room_details(room_id)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if self.failed_room_ids:
            text = "\n".join(
                [
                    "Couldn't gather details of the following rooms:",
                    "",
                    *[f"- {room_id}" for room_id in self.failed_room_ids],
                ]
            )
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        return not self.failed_room_ids

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!room_details <room_id1> [room_id2] ...`

**Purpose**:
Return the details of a room, cf doc of Synapse API for more info.

https://element-hq.github.io/synapse/latest/admin_api/rooms.html#room-details-api

**Examples**:
- `!room_details !id1:example.com`
- `!room_details !id1:example.com !id2:example.com`
"""
