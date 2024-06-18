import json
import time
from typing import Any

import aiofiles
import structlog
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot.command import CommandWithSteps
from matrix_admin_bot.command_step import CommandStep
from matrix_admin_bot.steps.totp import DEFAULT_MESSAGE, TOTPCommandStep
from matrix_admin_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class ServerNoticeState:
    notice: dict[str, str]
    recipients: list[str]


class ServerNoticeGetRecipientsStep(CommandStep):

    def __init__(self, command_state: ServerNoticeState, message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(message)
        self.command_state = command_state

    @override
    def validation_message(self) -> str:
        return "\n".join(
            [
                "Type your recipients with space separated : ",
                "- `all`",
                "- `@john.doe:matrix.org @jane.doe:matrix.org @judith.doe:matrix.org`"
            ]
        )

    @override
    async def validate(self, user_response: RoomMessage,
                       thread_root_message: RoomMessage,
                       room: MatrixRoom,
                       matrix_client: MatrixClient) -> bool:
        self.command_state.recipients = user_response.source.get("content", {}).get("body", "").split()
        return True


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


class ServerNoticeConfirmStep(TOTPCommandStep):
    def __init__(self, command_state: ServerNoticeState, totps: dict[str, str], message: str = DEFAULT_MESSAGE) -> None:
        super().__init__(totps, message)
        self.command_state = command_state

    @override
    def validation_message(self) -> str:
        return "\n".join(
            [
                super().validation_message(),
                "",
                "",
                self.command_state.notice["body"]
            ]
        )

    # # TODO: test - purpose to by pass otp validation
    # @override
    # async def validate(self, user_response: RoomMessage,
    #                    thread_root_message: RoomMessage,
    #                    room: MatrixRoom,
    #                    matrix_client: MatrixClient) -> bool:
    #     return True


class ServerNoticeCommand(CommandWithSteps):
    KEYWORD = "server_notice"

    def __init__(
            self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
            totps: dict[str, str] | None,
    ) -> None:
        super().__init__(room, message, matrix_client, totps)
        self.command_state = ServerNoticeState()
        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.command_state.recipients = event_parser.command(self.KEYWORD).split()

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.command_steps: list[CommandStep] = [ServerNoticeGetRecipientsStep(self.command_state),
                                                 ServerNoticeGetNoticeStep(self.command_state),
                                                 ServerNoticeConfirmStep(self.command_state, totps)]

    @override
    async def execute(self) -> bool:
        users = await self.get_users()
        result = len(users) > 0
        for user_id in users:
            result = result and await self.send_server_notice(self.command_state.notice, user_id)
        return result

    async def get_users(self) -> set[str]:
        users = set()
        if "all" in self.command_state.recipients:
            # Get list of users
            resp = await self.matrix_client.send(
                "GET",
                f"/_synapse/admin/v2/users?from=0&guests=false",
                headers={"Authorization": f"Bearer {self.matrix_client.access_token}"}
            )
            if not resp.ok:
                return users
            while True:
                data = await resp.json()
                users = users | {user["name"] for user in data["users"] if not user["user_type"]}
                if data.get("next_token"):
                    counter = data["next_token"]
                    resp = await self.matrix_client.send(
                        "GET",
                        f"/_synapse/admin/v2/users?from={counter}&guests=false",
                        headers={"Authorization": f"Bearer {self.matrix_client.access_token}"}
                    )
                    if not resp.ok:
                        return users
                else:
                    break
        else:
            for user_id in self.command_state.recipients:
                if user_id.startswith("@"):
                    users.add(user_id)
        return users

    async def send_server_notice(self, message: dict[str:Any], user_id: str) -> bool:
        if user_id.startswith("@_"):
            # Skip appservice users
            return True
        content: dict[str, Any] = {}
        for key in ["msgtype", "body", "format", "formatted_body"]:
            if key in message:
                content[key] = message[key]

        resp = None
        retry_nb = 0
        while retry_nb < 5:
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
            if resp.status == 429:
                retry_nb += 1
                # use some exp backoff
                time.sleep(0.5 * retry_nb)
            else:
                break

        self.json_report["details"].setdefault(user_id, {})

        # TODO handle unknown user here and return
        if resp.ok:
            json_body = await resp.json()
            self.json_report["details"][user_id]["status"] = "SUCCESS"
            self.json_report["details"][user_id]["response"] = str(json_body)
        else:
            json_body = await resp.json()
            self.json_report["details"][user_id]["status"] = "FAILED"
            self.json_report["details"][user_id]["response"] = str(json_body)
            self.json_report["failed_users"] = self.json_report["failed_users"] + user_id + " "
            return False

        return True

    @override
    async def send_result(self) -> None:
        logger.info(f"result={self.json_report}")
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
