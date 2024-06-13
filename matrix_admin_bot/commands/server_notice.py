import json
import secrets
import string
import time
from typing import Any

import aiofiles
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot.command import CommandToValidate
from matrix_admin_bot.util import get_server_name


class ServerNoticeCommand(CommandToValidate):
    KEYWORD = "server_notice"

    @staticmethod
    @override
    def needs_secure_validation() -> bool:
        # TODO
        # return True
        return False

    def __init__(
        self, room: MatrixRoom, message: RoomMessage, matrix_client: MatrixClient
    ) -> None:
        super().__init__(room, message, matrix_client)

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.message_content = event_parser.command(self.KEYWORD)
        print(self.message_content)

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}

        self.server_name = get_server_name(self.matrix_client.user_id)

    @override
    def validation_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to send a notice!",
            ]
        )
        # await self.matrix_client.send_markdown_message(
        #         self.room.room_id,
        #         str(self.json_report["result"]),
        #         reply_to=self.message.event_id,
        #         thread_root=self.message.event_id,
        #     )

    @override
    async def execute(self) -> bool:
        user_id = "@mag:my.matrix.host"
        await self.send_server_notice(self.message.source["content"], user_id)

    async def send_server_notice(self, message: str, user_id: str) -> bool:
        # print(message)
        resp = await self.matrix_client.send(
            "POST",
            f"/_synapse/admin/v1/send_server_notice",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            data=json.dumps(
                {
                    "user_id": user_id,
                    "content": message,
                }
            ),
        )

        result = "result"
        self.json_report.setdefault(result, {})

        # TODO handle unknown user here and return
        if resp.ok:
            json_body = await resp.json()
            self.json_report[result]["status"] = "SUCCESS"
            self.json_report[result]["response"] = str(json_body)
        else:
            json_body = await resp.json()
            self.json_report[result]["status"] = "FAILED"
            self.json_report[result]["response"] = str(json_body)
            return False

        return True

    @override
    async def send_result(self) -> None:
        async with aiofiles.tempfile.NamedTemporaryFile(suffix=".json") as tmpfile:
            await tmpfile.write(
                json.dumps(self.json_report, indent=2, sort_keys=True).encode()
            )
            await tmpfile.flush()
            await self.matrix_client.send_file_message(
                self.room.room_id,
                str(tmpfile.name),
                mime_type="application/json",
                filename=f"{time.strftime('%Y_%m_%d-%H_%M')}-{self.KEYWORD}.json",
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )
