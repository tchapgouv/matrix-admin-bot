from collections.abc import Mapping
from typing import Any, override

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot import InteractiveValidatedCommand
from matrix_admin_bot.admin_client import AdminClient
from matrix_admin_bot.commands.next.register_proconnect_only_domain import (
    POLICY_DATA_KEY,
    reply_markdown_in_thread,
    send_command_error,
)

logger = structlog.getLogger(__name__)


class RegisterListProconnectOnlyDomainsCommandV2(InteractiveValidatedCommand):
    """List the ProConnect-only domains of the MAS policy data.

    Every bot sharing the admin room executes the command and reports
    the domains of its own homeserver: the whole list across all the
    servers is shown.
    """

    KEYWORD = "register_list_proconnect_only_domains"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]

    @property
    @override
    def help_message(self) -> str:
        return f"""
**Usage**:
`!{self.KEYWORD}`

**Purpose**:
List the domains of the `{POLICY_DATA_KEY}` list of the MAS policy data.
Users with an email on a listed domain can only register via ProConnect:
the "continue with email" button is hidden on the register page.

Every bot sharing the admin room reports the domains of its own
homeserver: the whole list across all the servers is shown.
"""

    @override
    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        if self.command_text:
            await send_command_error(self, f"Invalid syntax. Usage: `!{self.KEYWORD}`")
            return True

        return await super().execute()

    @override
    async def simple_execute(self) -> bool:
        try:
            policy_data = await self.admin_client.get_latest_policy_data()
        except RuntimeError:
            logger.warning("Failed to get the current policy data from MAS")
            await reply_markdown_in_thread(
                self, "Failed to get the current policy data from MAS."
            )
            return False
        policy_data = policy_data if policy_data is not None else {}
        domains: list[str] = policy_data.get(POLICY_DATA_KEY, [])
        await reply_markdown_in_thread(self, self.list_message(domains))
        return True

    def list_message(self, domains: list[str]) -> str:
        if not domains:
            return (
                f"No ProConnect-only domain is set on homeserver "
                f"`{self.server_name}`: users can register with their email "
                "on any domain."
            )
        return "\n".join(
            [
                (
                    f"ProConnect-only domains (`{POLICY_DATA_KEY}`) of "
                    f"homeserver `{self.server_name}`:"
                ),
                *[f"- `{d}`" for d in domains],
            ]
        )
