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
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
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
        await self.get_user_ids_from_args(self.command_text.split())
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

        logger.debug(
            "User related command arguments parsed",
            command=self.__class__.__name__,
            keyword=self.keyword,
            user_ids=self.user_ids,
            email_args=email_args,
            domains=domains,
            all_local_users=all_local_users,
        )

        # TODO use sydent /info to check if a domain is this server responsability

        if all_local_users or domains:
            mas_user_id_to_emails: dict[str, list[str]] = {}
            logger.debug(
                "Retrieving user emails from MAS to resolve local users",
                command=self.__class__.__name__,
                all_local_users=all_local_users,
                domains=domains,
            )
            mas_user_emails = await self.admin_client.get_user_emails()
            logger.debug(
                "User emails retrieved from MAS",
                command=self.__class__.__name__,
                nb_user_emails=len(mas_user_emails),
            )

            for email, mas_id in mas_user_emails.items():
                domain = email.split("@")[1]
                if all_local_users or domain in domains:
                    mas_user_id_to_emails.setdefault(mas_id, []).append(email)

            logger.debug(
                "Matched MAS users against requested domains",
                command=self.__class__.__name__,
                nb_matched_users=len(mas_user_id_to_emails),
            )

            for mas_user_id, emails in mas_user_id_to_emails.items():
                user_id = await self.admin_client.get_user(
                    self.server_name, mas_user_id
                )
                if user_id:
                    self.user_ids.append(user_id)
                    self.mxid_to_emails[user_id] = emails
                else:
                    logger.warning(
                        "Cannot find the local user matching a MAS user",
                        command=self.__class__.__name__,
                        mas_user_id=mas_user_id,
                        emails=emails,
                    )

            logger.debug(
                "Local users resolved from MAS users",
                command=self.__class__.__name__,
                nb_local_users=len(self.mxid_to_emails),
            )

        if self.transform_cmd_input_fct:
            logger.debug(
                "Applying command input transformation function",
                command=self.__class__.__name__,
                email_args=email_args,
            )
            transformed_user_ids = await self.transform_cmd_input_fct(
                self.__class__, email_args
            )
            logger.debug(
                "Command input transformation function returned users",
                command=self.__class__.__name__,
                transformed_user_ids=transformed_user_ids,
            )
            self.user_ids.extend(transformed_user_ids)

        logger.debug(
            "User ids resolved from command arguments",
            command=self.__class__.__name__,
            keyword=self.keyword,
            user_ids=self.user_ids,
            mxid_to_emails=self.mxid_to_emails,
        )
