import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import structlog
from aiohttp import ClientResponse
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.command import ICommand
from matrix_command_bot.simple_command import SimpleExecuteStep
from matrix_command_bot.step import CommandAction, CommandWithSteps, ICommandStep
from matrix_command_bot.step.reaction_steps import (
    ReactionCommandState,
    ReactionStep,
    ResultReactionStep,
)
from matrix_command_bot.util import (
    get_server_name,
    is_local_user,
    randomword,
    send_report,
    set_status_reaction,
)
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.steps import ValidateStep

USER_ALL = "all"

logger = structlog.getLogger(__name__)


class ServerNoticeState(ReactionCommandState):
    def __init__(self) -> None:
        super().__init__()
        self.notice_content: Mapping[str, Any] = {}
        self.recipients: list[str] = []
        self.notice_original_event_id: str | None = None


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

        self.command_state.recipients = (
            reply.source.get("content", {}).get("body", "").split()
        )

        self.transform_cmd_input_fct: (
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
        ) = self.command.extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

        if self.transform_cmd_input_fct:
            self.command_state.recipients = await self.transform_cmd_input_fct(
                self.command.__class__, self.command_state.recipients
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

        self.command_state.notice_content = reply.source["content"]
        self.command_state.notice_original_event_id = reply.event_id
        return True, CommandAction.CONTINUE


class ShouldExecuteStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        command_state: ServerNoticeState,
        server_name: str | None,
    ) -> None:
        super().__init__(command)
        self.command_state = command_state
        self.server_name = server_name

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if self.command_state.recipients:
            if (
                USER_ALL in self.command_state.recipients
                and len(self.command_state.recipients) == 1
            ) or (self.server_name in self.command_state.recipients):
                return True, CommandAction.CONTINUE

            for user_id in self.command_state.recipients:
                if is_local_user(user_id, self.server_name):
                    return True, CommandAction.CONTINUE

        await set_status_reaction(
            self.command, "", self.command_state.current_reaction_event_id
        )
        return True, CommandAction.ABORT


class ServerNoticeCommandV2(CommandWithSteps):
    KEYWORD = "server_notice"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.validator: IValidator = extra_config.get("validator")  # pyright: ignore[reportAttributeAccessIssue]
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.limit: int = extra_config.get("server_notice_limit", 100)  # pyright: ignore[reportAttributeAccessIssue]

        self.state = ServerNoticeState()

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()

        self.command_text = event_parser.command(self.KEYWORD).strip()

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}
        self.json_report.setdefault("summary", {})
        self.json_report["summary"].setdefault("success", 0)
        self.json_report["summary"].setdefault("failed", 0)
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.command_id = randomword(16)

    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        return await super().execute()

    @override
    async def create_steps(self) -> list[ICommandStep]:
        return [
            ServerNoticeAskRecipientsStep(self),
            ServerNoticeGetRecipientsStep(self, self.state),
            ServerNoticeGetNoticeStep(self, self.state),
            ValidateStep(
                self,
                self.state,
                self.validator,
                (
                    "Please verify the previous message, "
                    "it will be sent as this to the users.\n"
                    "You can edit it if needed."
                ),
            ),
            ShouldExecuteStep(self, self.state, self.server_name),
            ReactionStep(self, self.state, "🚀"),
            SimpleExecuteStep(self, self.state, self.simple_execute),
            ResultReactionStep(self, self.state),
        ]

    # async def simple_execute(self) -> bool:
    #     logger.info("Server Notice - %s - started", self.command_id)
    #     users = await self.get_users(self.json_report, self.limit)
    #     nb_users = len(users)
    #     logger.info("Notice will be sent to %s users", nb_users)
    #     result = True
    #     if self.state.notice_content:
    #         for index, user_id in enumerate(users):
    #             has_been_sent = await self.send_server_notice(
    #                 self.state.notice_content, user_id
    #             )
    #             result = result and has_been_sent
    #             logger.info(
    #                 "Process Server Notice %s/%s : %s", index + 1, nb_users, user_id
    #             )
    #     else:
    #         self.json_report["summary"]["status"] = "FAILED"
    #         self.json_report["summary"]["reason"] = "There is no notice to send"
    #     logger.info("Server Notice - %s - completed", self.command_id)
    #
    #     if self.json_report:
    #         await send_report(
    #             json_report=self.json_report,
    #             report_name=self.KEYWORD,
    #             matrix_client=self.matrix_client,
    #             room_id=self.room.room_id,
    #             replied_event_id=self.message.event_id,
    #         )
    #     return result

    async def simple_execute(self) -> bool:
        logger.info("Server Notice - %s - started", self.command_id)
        users = await self.get_users(self.json_report, self.limit)
        users=list(users)
        nb_users = len(users)
        logger.info("Notice will be sent to %s users", nb_users)
        result = True

        if not self.state.notice_content:
            self.json_report["summary"]["status"] = "FAILED"
            self.json_report["summary"]["reason"] = "There is no notice to send"
        else:
            chunk_size = 4
            for chunk_start in range(0, nb_users, chunk_size):
                chunk = users[chunk_start:chunk_start + chunk_size]

                results = await asyncio.gather(
                    *[
                        self.send_server_notice(self.state.notice_content, user_id)
                        for user_id in chunk
                    ],
                    return_exceptions=True,
                )

                for index, (user_id, user_result) in enumerate(zip(chunk, results)):
                    if isinstance(user_result, Exception):
                        logger.exception(
                            "Unexpected error for %s", user_id, exc_info=user_result
                        )
                        self.json_report["summary"]["failed"] += 1
                        self.json_report["failed_users"] += user_id + " "
                        result = False
                    else:
                        result = result and user_result

                    logger.info(
                        "Process Server Notice %s/%s : %s",
                        chunk_start + index + 1,
                        nb_users,
                        user_id,
                    )

        logger.info("Server Notice - %s - completed", self.command_id)

        if self.json_report:
            await send_report(
                json_report=self.json_report,
                report_name=self.KEYWORD,
                matrix_client=self.matrix_client,
                room_id=self.room.room_id,
                replied_event_id=self.message.event_id,
            )
        return result

    async def get_users(
        self, json_report: dict[str, Any], limit: int = 100
    ) -> set[str]:
        users: set[str] = set()
        if self.state.recipients and (
            (USER_ALL in self.state.recipients and len(self.state.recipients) == 1)
            or (self.server_name in self.state.recipients)
        ):
            users = await self.admin_client.get_users(
                self.server_name, json_report, limit
            )
        elif self.state.recipients:
            for user_id in self.state.recipients:
                if is_local_user(user_id, self.server_name):
                    users.add(user_id)
        return users

    async def send_server_notice(
        self, message: Mapping[str, Any], user_id: str
    ) -> bool:
        if user_id.startswith("@_"):
            return True  # Skip appservice users

        content = {
            key: message[key]
            for key in ["msgtype", "body", "format", "formatted_body"]
            if key in message
        }

        resp = await self._send_with_retry(user_id, content)
        return await self._handle_response(user_id, resp)

    async def _send_with_retry(
        self, user_id: str, content: dict[str, Any]
    ) -> ClientResponse | None:
        resp = None
        for retry_nb in range(10):
            try:
                resp = await self.admin_client.send_to_synapse(
                    "POST",
                    "/_synapse/admin/v1/send_server_notice",
                    data=json.dumps({"user_id": user_id, "content": content}),
                )
                if resp.ok or (resp.status < 500 and resp.status != 429):
                    break
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Bot Admin has lost connection for %s", user_id, exc_info=e
                )
            await asyncio.sleep(0.5 * retry_nb)
        return resp

    # async def _handle_response(self, user_id: str, resp: ClientResponse | None) -> bool:
    #     if resp and resp.ok:
    #         self.json_report["summary"]["success"] += 1
    #         return True
    #     error_message = (
    #         str(await resp.json())
    #         if resp
    #         else "No response from /_synapse/admin/v1/send_server_notice"
    #     )
    #     logger.warning("Notice failed for %s: %s", user_id, error_message)
    #     self.json_report["summary"]["failed"] += 1
    #     self.json_report["failed_users"] += user_id + " "
    #     return False

    async def _handle_response(self, user_id: str, resp: ClientResponse) -> tuple[bool, str]:
        if resp and resp.ok:
            return True, user_id
        else:
            error_message = (
                str(await resp.json()) if resp else
                "No response from /_synapse/admin/v1/send_server_notice"
            )
            logger.info("Notice failed for %s: %s", user_id, error_message)
            return False, user_id

    async def send_help(self) -> None:
        """Send the command's help message."""
        if self.extra_config.get("is_coordinator", True):
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                self.help_message,
            )

    @property
    def help_message(self) -> str:
        return """
**Usage**:
`!server_notice`

**Purpose**:
Sends server notices to users through an interactive, step-by-step process.

**Steps**:
1. The command will first ask you to specify recipients
2. Then you'll be asked to provide the message content
3. The command will then confirm and send the notices

**Recipients can be specified as**:
- `all` - sends to all users on the server(s)
- `server1.org server2.org` - sends to all users on the specified servers
- `@user1:server1.org user2@server2.org` - sends to specific users

**Notes**:
- Server notices appear as system messages to users
- Use this feature responsibly for important announcements
- The message is entered in a second step after specifying recipients
- You can edit your message before confirming
"""

    @override
    async def replace_received(
        self,
        new_content: Mapping[str, Any],
        original_event: RoomMessage,
    ) -> None:
        if (
            self.state.notice_original_event_id
            and self.state.notice_original_event_id == original_event.event_id
        ):
            self.state.notice_content = new_content
