from collections.abc import Awaitable, Callable, Mapping
from typing import Any, override

import structlog
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.admin_client import AdminClient
from matrix_command_bot.command import ICommand
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

    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        return await super().execute()

    async def send_help(self) -> None:
        """Send the command's help message."""
        if self.extra_config.get("is_coordinator", True):
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                self.help_message,
            )

    async def send_report(self) -> None:
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
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
        ) = extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

    @override
    async def should_execute(self) -> bool:
        await self.get_user_ids_from_args(self.command_text.split())
        return any(
            is_local_user(user_id, self.server_name) for user_id in self.user_ids
        )

    # TODO reduce complexity
    async def get_user_ids_from_args(self, args: list[str]) -> None:  # noqa: C901
        email_args: list[str] = []
        domains: set[str] = set()
        all_local_users = False
        for arg in args:
            if arg in ["all", self.server_name]:
                all_local_users = True
                break

            if len(arg) > 0 and arg[0] == "@" and ":" in arg:
                self.user_ids.append(arg)
            elif "@" in arg:
                email_args.append(arg)
            else:
                domains.add(arg)

        # TODO use sydent /info to check if a domain is this server responsability

        if all_local_users or domains:
            mas_user_id_to_emails: dict[str, list[str]] = {}
            mas_user_emails = await self.admin_client.get_user_emails()

            for email, mas_id in mas_user_emails.items():
                domain = email.split("@")[1]
                if all_local_users or domain in domains:
                    mas_user_id_to_emails.setdefault(mas_id, []).append(email)

            for mas_user_id, emails in mas_user_id_to_emails.items():
                user_id = await self.admin_client.get_user(
                    self.server_name, mas_user_id
                )
                if user_id:
                    self.user_ids.append(user_id)
                    self.mxid_to_emails[user_id] = emails

        if self.transform_cmd_input_fct:
            self.user_ids.extend(
                await self.transform_cmd_input_fct(self.__class__, email_args)
            )
