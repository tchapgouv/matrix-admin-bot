import json
from collections.abc import Mapping
from typing import Any, override

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.commands.next.base.policy_data import (
    JSONValue,
    PolicyDataCommand,
    PolicyValueError,
    parse_policy_key,
)


class PolicyRemoveCommandV2(PolicyDataCommand):
    """Remove a value from a list of the MAS policy data."""

    KEYWORD = "policy_remove"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.value: str | None = None

    @override
    def parse_args(self, args: list[str]) -> str | None:
        if len(args) != 3:
            return (
                f"Invalid syntax. Usage: `!{self.KEYWORD} <policy_key> <value> "
                "<homeserver>`"
            )
        policy_key = parse_policy_key(args[0])
        if policy_key is None:
            return f"Invalid policy key: `{args[0]}`."
        self.policy_key = policy_key
        self.value = args[1]
        self.homeserver = args[2]
        return None

    @override
    def update_value(self, current: JSONValue) -> tuple[bool, JSONValue]:
        value = self.value
        if value is None:
            # Should not happen: parse_args sets it before running the steps
            return False, current
        if current is None:
            return False, None
        if not isinstance(current, list):
            raise PolicyValueError(
                f"The value of `{self.policy_key_str}` on homeserver "
                f"`{self.homeserver}` is not a list: {json.dumps(current)}."
            )
        if value not in current:
            return False, current
        return True, [v for v in current if v != value]

    @override
    def no_change_message(self, current: JSONValue) -> str:
        values = current if isinstance(current, list) else []
        return "\n".join(
            [
                (
                    f"The value `{self.value}` is not in the "
                    f"`{self.policy_key_str}` list of homeserver "
                    f"`{self.homeserver}`."
                ),
                "",
                "Current values:",
                *[f"- `{v}`" for v in values],
            ]
        )

    @override
    def success_message(self, new_value: JSONValue) -> str:
        values = new_value if isinstance(new_value, list) else []
        return "\n".join(
            [
                (
                    f"The value `{self.value}` has been **removed** from the "
                    f"`{self.policy_key_str}` list of homeserver "
                    f"`{self.homeserver}`."
                ),
                "",
                "Current values:",
                *[f"- `{v}`" for v in values],
            ]
        )

    @property
    @override
    def confirm_message(self) -> str | None:
        return (
            f"You are about to **remove** the value `{self.value}` from the "
            f"`{self.policy_key_str}` policy of homeserver "
            f"`{self.homeserver}`."
        )

    @property
    @override
    def help_message(self) -> str:
        return f"""
**Usage**:
`!{self.KEYWORD} <policy_key> <value> <homeserver>`

**Purpose**:
Remove a value from a list of the MAS policy data, e.g.
`registration.allowed_usernames` or `register_proconnect_only_domains`.

**Parameters**:
- `<policy_key>`: the dotted path of the policy data key, e.g.
  `registration.allowed_usernames`.
- `<value>`: the value to remove from the list, exactly as it appears in
  the current values (see the last command report).
- `<homeserver>`: the server name of the homeserver whose MAS is updated.
  Only the bot of this homeserver executes the command, on its own MAS.

**Examples**:
- `!{self.KEYWORD} register_proconnect_only_domains ac-versailles\\\\.fr example.org`
- `!{self.KEYWORD} registration.allowed_usernames ^agent- example.org`
"""
