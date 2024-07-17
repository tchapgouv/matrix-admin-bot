import asyncio
import json
import time
from collections.abc import Mapping
from typing import Any

import aiofiles
import structlog
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.simple_command import SimpleExecuteStep
from matrix_command_bot.step import CommandAction, CommandWithSteps, ICommandStep
from matrix_command_bot.step.simple_steps import ReactionStep, ResultReactionStep
from matrix_command_bot.util import get_server_name
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.steps import ValidateStep

USER_ALL = "all"

logger = structlog.getLogger(__name__)


class ServerNoticeState:
    notice_event: RoomMessage | None
    recipients: list[str] | None

    def __init__(self) -> None:
        self.notice_event = None
        self.recipients = None


class ServerNoticeAskRecipientsStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
    ) -> None:
        super().__init__(command)

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if self.command.extra_config.get("is_coordinator", True):
            message = """Type your recipients with space separated :
                      - `all`
                      - `matrix.org element.io homeserver.org`
                      - `@john.doe:matrix.org @jane.doe:matrix.org @june.doe:matrix.org`
                      """

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
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if not reply:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY
        if reply and self.command.message.sender != reply.sender:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        self.command_state.recipients = (
            reply.source.get("content", {}).get("body", "").split()
        )
        if self.command.extra_config.get("is_coordinator", True):
            message = "Type your notice"
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


class ServerNoticeGetNoticeStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        command_state: ServerNoticeState,
    ) -> None:
        super().__init__(command)
        self.command_state = command_state

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if not reply:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY
        if reply and self.command.message.sender != reply.sender:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        self.command_state.notice_event = reply
        return True, CommandAction.CONTINUE


class ServerNoticeCommand(CommandWithSteps):
    KEYWORD = "server_notice"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.secure_validator: IValidator = extra_config.get("secure_validator")  # type: ignore[reportAssignmentType]

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

        class _ValidateStep(ValidateStep):
            @property
            @override
            def message(self) -> str | None:
                return (
                    "Please verify the previous message, "
                    "it will be sent as this to the users.\n"
                    "You can edit it if needed."
                )

        return [
            ServerNoticeAskRecipientsStep(self),
            ServerNoticeGetRecipientsStep(self, command.state),
            ServerNoticeGetNoticeStep(self, command.state),
            _ValidateStep(self, self.secure_validator),
            ReactionStep(self, "🚀"),
            SimpleExecuteStep(self, self.simple_execute),
            ResultReactionStep(self),
        ]

    async def simple_execute(self) -> bool:
        users = await self.get_users()
        result = len(users) > 0
        if self.state.notice_event:
            for user_id in users:
                result = result and await self.send_server_notice(
                    self.state.notice_event.source["content"], user_id
                )
        else:
            self.json_report["details"]["status"] = "FAILED"
            self.json_report["details"]["reason"] = "There is no notice to send"

        if self.json_report and result:
            await self.send_report()
        return result

    async def get_users(self) -> set[str]:
        users: set[str] = set()
        if self.state.recipients and (
            (USER_ALL in self.state.recipients and len(self.state.recipients) == 1)
            or (self.server_name in self.state.recipients)
        ):
            # Get list of users
            resp = await self.matrix_client.send(
                "GET",
                "/_synapse/admin/v2/users?from=0&guests=false",
                headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            )
            if not resp.ok:
                return users
            while True:
                data = await resp.json()
                if "users" in data:
                    users = users | {
                        user["name"] for user in data["users"] if not user["user_type"]
                    }
                if data.get("next_token"):
                    counter = data["next_token"]
                    resp = await self.matrix_client.send(
                        "GET",
                        f"/_synapse/admin/v2/users?from={counter}&guests=false",
                        headers={
                            "Authorization": f"Bearer {self.matrix_client.access_token}"
                        },
                    )
                    if not resp.ok:
                        return users
                else:
                    break
        elif self.state.recipients:
            for user_id in self.state.recipients:
                if (
                    user_id.startswith("@")
                    and get_server_name(user_id) == self.server_name
                ):
                    users.add(user_id)
        return users

    async def send_server_notice(self, message: dict[str, Any], user_id: str) -> bool:
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
                "/_synapse/admin/v1/send_server_notice",
                headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
                data=json.dumps({"user_id": user_id, "content": content}),
            )
            if resp.status == 429:
                retry_nb += 1
                # use some exp backoff
                await asyncio.sleep(0.5 * retry_nb)
            else:
                break

        self.json_report["details"].setdefault(user_id, {})

        # TODO handle unknown user here and return
        if resp and resp.ok:
            json_body = await resp.json()
            self.json_report["details"][user_id]["status"] = "SUCCESS"
            self.json_report["details"][user_id]["response"] = str(json_body)
        elif resp:
            json_body = await resp.json()
            self.json_report["details"][user_id]["status"] = "FAILED"
            self.json_report["details"][user_id]["response"] = str(json_body)
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
        else:
            self.json_report["details"]["status"] = "FAILED"
            self.json_report["details"]["reason"] = (
                "No response /_synapse/admin/v1/send_server_notice"
            )

        return True

    async def send_report(self) -> None:
        logger.info("result=%s", self.json_report)
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

    @override
    async def replace_received(
        self, replace: RoomMessage, original: RoomMessage
    ) -> None:
        if (
            self.state.notice_event
            and self.state.notice_event.event_id == original.event_id
        ):
            self.state.notice_event = replace
