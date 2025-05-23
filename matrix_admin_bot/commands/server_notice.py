import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import structlog
from aiohttp import ClientConnectionError
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

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
        logger.debug("Executing ServerNoticeAskRecipientsStep")
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
        logger.debug("Executing ServerNoticeGetRecipientsStep", reply=reply)
        if not reply:
            logger.debug("No reply received, waiting for next reply")
            return True, CommandAction.WAIT_FOR_NEXT_REPLY
        if reply and self.command.message.sender != reply.sender:
            logger.debug(
                "Reply from different sender, waiting for next reply",
                reply_sender=reply.sender,
                original_sender=self.command.message.sender,
            )
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        self.command_state.recipients = (
            reply.source.get("content", {}).get("body", "").split()
        )
        logger.debug("Parsed recipients", recipients=self.command_state.recipients)

        self.transform_cmd_input_fct: (
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
        ) = self.command.extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

        if self.transform_cmd_input_fct:
            logger.debug("Transforming command input")
            self.command_state.recipients = await self.transform_cmd_input_fct(
                self.command.__class__, self.command_state.recipients
            )
            logger.debug(
                "Transformed recipients", recipients=self.command_state.recipients
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
        logger.debug("Executing ServerNoticeGetNoticeStep", reply=reply)
        if not reply:
            logger.debug("No reply received, waiting for next reply")
            return True, CommandAction.WAIT_FOR_NEXT_REPLY
        if reply and self.command.message.sender != reply.sender:
            logger.debug(
                "Reply from different sender, waiting for next reply",
                reply_sender=reply.sender,
                original_sender=self.command.message.sender,
            )
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        self.command_state.notice_content = reply.source["content"]
        self.command_state.notice_original_event_id = reply.event_id
        logger.debug(
            "Stored notice content",
            event_id=reply.event_id,
            content_type=reply.source["content"].get("msgtype"),
        )
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
        logger.debug(
            "Executing ShouldExecuteStep",
            recipients=self.command_state.recipients,
            server_name=self.server_name,
        )
        if self.command_state.recipients:
            if (
                USER_ALL in self.command_state.recipients
                and len(self.command_state.recipients) == 1
            ) or (self.server_name in self.command_state.recipients):
                logger.debug("Execution allowed - all users or server name match")
                return True, CommandAction.CONTINUE

            for user_id in self.command_state.recipients:
                if is_local_user(user_id, self.server_name):
                    logger.debug(
                        "Execution allowed - local user found", user_id=user_id
                    )
                    return True, CommandAction.CONTINUE

        logger.debug("Execution not allowed - no valid recipients")
        await set_status_reaction(
            self.command, "", self.command_state.current_reaction_event_id
        )
        return True, CommandAction.ABORT


class ServerNoticeCommand(CommandWithSteps):
    KEYWORD = "server_notice"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing ServerNoticeCommand",
            room_id=room.room_id,
            message_id=message.event_id,
        )
        super().__init__(room, message, matrix_client, extra_config)
        self.secure_validator: IValidator = extra_config.get("secure_validator")  # pyright: ignore[reportAttributeAccessIssue]

        self.state = ServerNoticeState()

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()

        self.command_text = event_parser.command(self.KEYWORD).strip()
        logger.debug("Parsed command text", command_text=self.command_text)

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}
        self.json_report.setdefault("summary", {})
        self.json_report["summary"].setdefault("success", 0)
        self.json_report["summary"].setdefault("failed", 0)
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")

        self.server_name = get_server_name(self.matrix_client.user_id)
        logger.debug("Got server name", server_name=self.server_name)

    async def execute(self) -> bool:
        logger.debug("Executing ServerNoticeCommand")
        if self.command_text == "help":
            logger.debug("Help command requested")
            await self.send_help()
            return True

        return await super().execute()

    @override
    async def create_steps(self) -> list[ICommandStep]:
        logger.debug("Creating command steps")
        return [
            ServerNoticeAskRecipientsStep(self),
            ServerNoticeGetRecipientsStep(self, self.state),
            ServerNoticeGetNoticeStep(self, self.state),
            ValidateStep(
                self,
                self.state,
                self.secure_validator,
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

    async def simple_execute(self) -> bool:
        logger.debug("Executing simple_execute")
        users = await self.get_users()
        logger.debug("Got users to notify", users=users)
        result = True
        if self.state.notice_content:
            for user_id in users:
                logger.debug("Sending server notice to user", user_id=user_id)
                result = result and await self.send_server_notice(
                    self.state.notice_content, user_id
                )
        else:
            logger.warning("No notice content to send")
            self.json_report["summary"]["status"] = "FAILED"
            self.json_report["summary"]["reason"] = "There is no notice to send"

        if self.json_report and result:
            logger.debug("Sending report", report=self.json_report)
            await send_report(
                json_report=self.json_report,
                report_name=self.KEYWORD,
                matrix_client=self.matrix_client,
                room_id=self.room.room_id,
                replied_event_id=self.message.event_id,
            )
        return result

    async def get_users(self) -> set[str]:
        logger.debug("Getting users to notify")
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
                        user["name"]
                        for user in data["users"]
                        if not user["user_type"] and not user["deactivated"]
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
                if is_local_user(user_id, self.server_name):
                    users.add(user_id)

        return users

    async def send_server_notice(
        self, message: Mapping[str, Any], user_id: str
    ) -> bool:
        logger.debug("Sending server notice", user_id=user_id)
        if user_id.startswith("@_"):
            # Skip appservice users
            logger.debug("Skipping appservice user", user_id=user_id)
            return True

        content: dict[str, Any] = {}
        for key in ["msgtype", "body", "format", "formatted_body"]:
            if key in message:
                content[key] = message[key]

        resp = None
        for retry_nb in range(10):
            try:
                resp = await self.matrix_client.send(
                    "POST",
                    "/_synapse/admin/v1/send_server_notice",
                    headers={
                        "Authorization": f"Bearer {self.matrix_client.access_token}"
                    },
                    data=json.dumps({"user_id": user_id, "content": content}),
                )
                if resp.ok:
                    break
                # Let's also stop there if we get a client error that
                # is not a rate limit.
                if resp.status < 500 and resp.status != 429:
                    break
            except ClientConnectionError as e:
                logger.warning("Bot Admin has lost connection for %s: %s", user_id, e)

            # use some backoff
            await asyncio.sleep(0.5 * retry_nb)

        # TODO handle unknown user here and return
        if resp and resp.ok:
            json_body = await resp.json()
            logger.info("Notice sent for %s: %s", user_id, str(json_body))
            self.json_report["summary"]["success"] = (
                self.json_report["summary"]["success"] + 1
            )

        elif resp:
            json_body = await resp.json()
            logger.info("Notice sent for %s: %s", user_id, str(json_body))
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
        else:
            error_message = "No response from /_synapse/admin/v1/send_server_notice"
            logger.info("Notice failed for %s: %s", user_id, error_message)
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )

        return True

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
            logger.debug("Replace notice content", reply_id=original_event.event_id)
            self.state.notice_content = new_content

    @override
    async def reply_received(self, reply: RoomMessage) -> None:
        logger.debug("Received reply", reply_id=reply.event_id)
        await super().reply_received(reply)
