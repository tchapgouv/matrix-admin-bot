import json
import secrets
import string
import time
from typing import Any

import aiofiles
import structlog
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot import validation
from matrix_command_bot.command import ICommand
from matrix_command_bot.simple_command import SimpleExecuteStep
from matrix_command_bot.step import CommandWithSteps, ICommandStep, CommandAction
from matrix_command_bot.step.simple_steps import ReactionStep, ResultReactionStep
from matrix_command_bot.util import get_server_name
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.steps import ConfirmStep, ValidateStep

logger = structlog.getLogger(__name__)


class ServerNoticeState:
    notice: dict[str, str]
    recipients: list[str]


class ServerNoticeAskRecipientsStep(ICommandStep):

    def __init__(
            self,
            command: ICommand,
    ) -> None:
        super().__init__(command)

    @override
    async def execute(self, reply: RoomMessage | None = None) -> tuple[bool, CommandAction]:
        message = "\n".join(
            [
                "Type your recipients with space separated : ",
                "- `all`",
                "- `@john.doe:matrix.org @jane.doe:matrix.org @judith.doe:matrix.org`"
            ]
        )

        await self.command.matrix_client.send_markdown_message(
            self.command.room.room_id,
            message,
            reply_to=self.command.message.event_id,
            thread_root=self.command.message.event_id,
        )
        return (
            True,
            CommandAction.CONTINUE,
        )


class ServerNoticeGetRecipientsStep(ICommandStep):

    def __init__(
            self,
            command: ICommand,
            command_state: ServerNoticeState,
    ) -> None:
        super().__init__(command)
        self.command_state = command_state

    @override
    async def execute(self, reply: RoomMessage | None = None) -> tuple[bool, CommandAction]:
        if not reply:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY
        if reply and self.command.message.sender != reply.sender:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        self.command_state.recipients = reply.source.get("content", {}).get("body", "").split()
        message = "\n".join(
            [
                "Type your notice",
            ]
        )

        await self.command.matrix_client.send_markdown_message(
            self.command.room.room_id,
            message,
            reply_to=self.command.message.event_id,
            thread_root=self.command.message.event_id,
        )
        return (
            True,
            CommandAction.CONTINUE,
        )


class ServerNoticeGetNoticeStep(ConfirmStep):

    def __init__(
            self,
            command: ICommand,
            validator: IValidator,
            command_state: ServerNoticeState,
    ) -> None:
        super().__init__(command, validator)
        self.command_state = command_state

    @property
    def message(self) -> str | None:
        return self.command_state.notice["body"]

    @override
    async def execute(self, reply: RoomMessage | None = None) -> tuple[bool, CommandAction]:
        if not reply:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY
        if reply and self.command.message.sender != reply.sender:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        self.command_state.notice = reply.source["content"]
        return await super().execute()


class ServerNoticeCommand(CommandWithSteps):
    KEYWORD = "server_notice"

    def __init__(
            self,
            room: MatrixRoom,
            message: RoomMessage,
            matrix_client: MatrixClient,
    ) -> None:
        if not validation.SECURE_VALIDATOR:
            raise Exception

        super().__init__(room, message, matrix_client)
        self.validator = validation.SECURE_VALIDATOR
        self.state = ServerNoticeState()

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.user_ids = event_parser.command(self.KEYWORD).split()

        self.failed_user_ids: list[str] = []

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")

        self.server_name = get_server_name(self.matrix_client.user_id)

    @override
    async def create_steps(self) -> list[ICommandStep]:
        command = self

        return [
            ServerNoticeAskRecipientsStep(self),
            ServerNoticeGetRecipientsStep(self, command.state),
            ServerNoticeGetNoticeStep(self, self.validator, command.state),
            ValidateStep(self, self.validator),
            ReactionStep(self, "🚀"),
            SimpleExecuteStep(self, self.simple_execute),
            ResultReactionStep(self),
        ]

    async def get_users(self) -> set[str]:
        users = set()
        if "all" in self.state.recipients:
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
            for user_id in self.state.recipients:
                if user_id.startswith("@"):
                    users.add(user_id)
        return users

    async def send_notice(
            self, user_id: str, password: str, *, logout_devices: bool = True
    ) -> bool:
        # TODO check coordinator config
        if get_server_name(user_id) != self.server_name:
            return True

        resp = await self.matrix_client.send(
            "GET",
            f"/_synapse/admin/v2/users/{user_id}/devices",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
        )

        self.json_report.setdefault(user_id, {})

        # TODO handle unknown user here and return
        if resp.ok:
            json_body = await resp.json()
            self.json_report[user_id]["devices"] = json_body.get("devices", [])

        resp = await self.matrix_client.send(
            "POST",
            f"/_synapse/admin/v1/reset_password/{user_id}",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            data=json.dumps(
                {
                    "new_password": password,
                    "logout_devices": logout_devices,
                }
            ),
        )
        if not resp.ok:
            json_body = await resp.json()
            self.json_report[user_id].update(json_body)
            self.failed_user_ids.append(user_id)
            return False

        return True

    @override
    async def simple_execute(self) -> bool:
        users = await self.get_users()
        result = len(users) > 0
        for user_id in users:
            result = result and await self.send_server_notice(self.state.notice, user_id)

        if self.json_report:
            await self.send_report()
        return result

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

        return True

    async def send_report(self) -> None:
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
