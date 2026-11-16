import json
from collections.abc import Mapping
from typing import Any, override

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot import InteractiveValidatedCommand
from matrix_admin_bot.admin_client import AdminClient
from matrix_admin_bot.commands.next.base.policy_data import (
    JSONValue,
    get_at_path,
    parse_policy_key,
    reply_markdown_in_thread,
    send_command_error,
)

logger = structlog.getLogger(__name__)


class PolicyGetCommandV2(InteractiveValidatedCommand):
    """Get the value of any key of the MAS policy data.

    Every bot sharing the admin room executes the command and reports
    the value of its own homeserver: the values across all the servers
    are shown.
    """

    KEYWORD = "policy_get"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.policy_key: list[str] = []

    @property
    @override
    def help_message(self) -> str:
        return f"""
**Usage**:
`!{self.KEYWORD} <policy_key>`

**Purpose**:
Get the value of any key of the MAS policy data, e.g.
`registration.allowed_usernames` or `register_proconnect_only_domains`.

Every bot sharing the admin room reports the value of its own homeserver:
the values across all the servers are shown.

**Parameters**:
- `<policy_key>`: the dotted path of the policy data key, e.g.
  `registration.allowed_usernames`.

**Examples**:
- `!{self.KEYWORD} register_proconnect_only_domains`
- `!{self.KEYWORD} registration.allowed_usernames`
"""

    @override
    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        args = self.command_text.split()
        if len(args) != 1:
            await send_command_error(
                self, f"Invalid syntax. Usage: `!{self.KEYWORD} <policy_key>`"
            )
            return True
        policy_key = parse_policy_key(args[0])
        if policy_key is None:
            await send_command_error(self, f"Invalid policy key: `{args[0]}`.")
            return True
        self.policy_key = policy_key

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
        value = get_at_path(policy_data, self.policy_key)
        await reply_markdown_in_thread(self, self.value_message(value))
        return True

    def value_message(self, value: JSONValue) -> str:
        key = ".".join(self.policy_key)
        if value is None:
            return (
                f"The `{key}` policy is not set on homeserver "
                f"`{self.server_name}`: the policy default applies."
            )
        return "\n".join(
            [
                f"Value of the `{key}` policy on homeserver `{self.server_name}`:",
                "",
                "```json",
                json.dumps(value, indent=2),
                "```",
            ]
        )
