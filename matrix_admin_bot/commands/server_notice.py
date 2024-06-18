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

from matrix_admin_bot.command import CommandWithSteps
from matrix_admin_bot.command_step import CommandStep
from matrix_admin_bot.util import get_server_name
from matrix_admin_bot.steps.confirm import ConfirmCommandStep
from matrix_admin_bot.steps.totp import TOTPCommandStep, DEFAULT_MESSAGE


class ServerNoticeState:
    notice: dict[str, str]


class ServerNoticeGetNoticeStep(CommandStep):

    def __init__(self, command_state: ServerNoticeState, message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)
        self.command_state = command_state

    @override
    def validation_message(self) -> str:
        return "\n".join(
            [
                "Type your notice",
            ]
        )

    @override
    async def validate(self, user_response: RoomMessage,
                         thread_root_message: RoomMessage,
                         room: MatrixRoom,
                         matrix_client: MatrixClient) -> bool:
        self.command_state.notice = user_response.source["content"]
        return True


class ServerNoticeConfirmStep(ConfirmCommandStep):

    def __init__(self, command_state: ServerNoticeState, message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)
        self.command_state = command_state

    @override
    def validation_message(self) -> str :
        return "\n".join(
            [
                f"Are you ok with the following notice ? Type {ConfirmCommandStep.CONFIRM_KEYWORDS}",
                "",
                self.command_state.notice["body"]
            ]
        )


class ServerNoticeCommand(CommandWithSteps):
    KEYWORD = "server_notice"

    # @staticmethod
    # @override
    # def needs_secure_validation() -> bool:
    #     return True

    def __init__(
            self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
            totps: dict[str, str] | None,
    ) -> None:
        super().__init__(room, message, matrix_client, totps)
        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.message_content = event_parser.command(self.KEYWORD)

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.command_state = ServerNoticeState()
        self.command_steps: list[CommandStep] = [ServerNoticeGetNoticeStep(self.command_state),
                                                     ServerNoticeConfirmStep(self.command_state),
                                                     # TOTPCommandStep(totps)
                                                     ]

    @override
    async def execute(self) -> bool:
        user_id = "@mag:my.matrix.host"
        return await self.send_server_notice(self.command_state.notice, user_id)

    async def send_server_notice(self, message: str, user_id: str) -> bool:
        # print(message)
        content:dict[str, Any] = {}
        for key in ["msgtype", "body", "format", "formatted_body"]:
            if key in message:
                content[key] = message[key]

        resp = await self.matrix_client.send(
            "POST",
            f"/_synapse/admin/v1/send_server_notice",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            data=json.dumps(
                {
                    "user_id": user_id,
                    "content": content
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


