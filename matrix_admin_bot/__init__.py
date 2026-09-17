from collections.abc import Awaitable, Callable, Mapping
from typing import Any, override

import structlog
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.admin_client import AdminClient
from matrix_command_bot.util import get_server_name, is_local_user, send_report
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand

logger = structlog.getLogger(__name__)


class InteractiveValidatedCommand(SimpleValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        keyword: str,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]

        self.keyword = keyword

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.command_text = event_parser.command(keyword).strip()

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.json_report: dict[str, Any] = {}

        logger.debug(
            "Interactive validated command initialized",
            command=self.__class__.__name__,
            keyword=self.keyword,
            room_id=self.room.room_id,
            event_id=self.message.event_id,
            sender=self.message.sender,
            server_name=self.server_name,
        )

    async def execute(self) -> bool:
        if self.command_text == "help":
            logger.debug(
                "Command help requested",
                command=self.__class__.__name__,
                keyword=self.keyword,
                room_id=self.room.room_id,
            )
            await self.send_help()
            return True

        return await super().execute()

    async def send_help(self) -> None:
        """Send the command's help message."""
        if self.extra_config.get("is_coordinator", True):
            logger.debug(
                "Sending command help message",
                command=self.__class__.__name__,
                keyword=self.keyword,
                room_id=self.room.room_id,
            )
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                self.help_message,
            )
        else:
            logger.debug(
                "Not sending command help message, bot is not a coordinator",
                command=self.__class__.__name__,
                keyword=self.keyword,
                room_id=self.room.room_id,
            )

    async def send_report(self) -> None:
        logger.debug(
            "Sending command report",
            command=self.__class__.__name__,
            keyword=self.keyword,
            room_id=self.room.room_id,
            has_report=bool(self.json_report),
        )
        await send_report(
            json_report=self.json_report,
            report_name=self.keyword,
            matrix_client=self.matrix_client,
            room_id=self.room.room_id,
            replied_event_id=self.message.event_id,
        )

    @property
    def help_message(self) -> str:
        """Return the help message for this command.

        This should be overridden by subclasses to provide specific help text.
        """
        return f"**Usage**:\n`!{self.keyword} <user1> [user2] ...`"


class UserRelatedCommand(InteractiveValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        keyword: str,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, keyword, extra_config)
        server_name = get_server_name(self.matrix_client.user_id)
        assert server_name  # noqa: S101
        self.server_name: str = server_name
        self.user_ids: list[str] = []
        self.mxid_to_emails: dict[str, list[str]] = {}

        self.transform_cmd_input_fct: (
            Callable[[list[str]], Awaitable[list[str]]] | None
        ) = extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

        logger.debug(
            "User related command initialized",
            command=self.__class__.__name__,
            keyword=keyword,
            server_name=self.server_name,
            has_transform_cmd_input_fct=self.transform_cmd_input_fct is not None,
        )

    @override
    async def should_execute(self) -> bool:
        (
            self.user_ids,
            self.mxid_to_emails,
        ) = await self.admin_client.get_mxids_from_args(
            self.command_text.split(), self.server_name, self.transform_cmd_input_fct
        )
        should_execute = any(
            is_local_user(user_id, self.server_name) for user_id in self.user_ids
        )
        logger.debug(
            "Determined whether user related command should execute",
            command=self.__class__.__name__,
            keyword=self.keyword,
            user_ids=self.user_ids,
            should_execute=should_execute,
        )
        return should_execute
