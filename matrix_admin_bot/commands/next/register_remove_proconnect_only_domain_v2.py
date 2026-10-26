from collections.abc import Mapping
from typing import Any, override

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.commands.next.register_proconnect_only_domain import (
    POLICY_DATA_KEY,
    RegisterProconnectOnlyDomainCommand,
)


class RegisterRemoveProconnectOnlyDomainCommandV2(RegisterProconnectOnlyDomainCommand):
    KEYWORD = "register_remove_proconnect_only_domain"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)

    @override
    def update_domains(self, domain: str, domains: list[str]) -> list[str] | None:
        if domain not in domains:
            return None
        return [d for d in domains if d != domain]

    @override
    def no_change_message(self, domain: str, domains: list[str]) -> str:
        return "\n".join(
            [
                (
                    f"The domain `{domain}` is not in the `{POLICY_DATA_KEY}` "
                    f"list of homeserver `{self.server_name}`."
                ),
                "",
                "Current domains:",
                *[f"- `{d}`" for d in domains],
            ]
        )

    @override
    def success_message(self, domain: str, new_domains: list[str]) -> str:
        return "\n".join(
            [
                (
                    f"The domain `{domain}` has been **removed** from the "
                    f"`{POLICY_DATA_KEY}` list of homeserver "
                    f"`{self.server_name}`."
                ),
                "",
                "Current domains:",
                *[f"- `{d}`" for d in new_domains],
            ]
        )

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                (
                    f"You are about to **remove** the domain `{self.domain}` "
                    f"from the `{POLICY_DATA_KEY}` list of homeserver "
                    f"`{self.server_name}`."
                ),
                "",
                (
                    "Users with an email on this domain will be able to "
                    "register with their email again."
                ),
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return f"""
**Usage**:
`!{self.KEYWORD} <domain_regexp> [homeserver]`

**Purpose**:
Remove a domain from the `{POLICY_DATA_KEY}` list of the MAS policy data.
Users with an email on a listed domain can only register via ProConnect:
the "continue with email" button is hidden on the register page.
When the list is empty, all the users can register with their email.

**Parameters**:
- `<domain_regexp>`: the regexp exactly as it appears in the current
  domain list (see the current domains in the last command report).
- `[homeserver]`: optional homeserver server name. By default the
  homeserver in charge of the email domain is guessed from the identity
  server; when given, this homeserver is targeted explicitly, without
  querying the identity server.

**Examples**:
- `!{self.KEYWORD} ac-versailles\\.fr`
- `!{self.KEYWORD} .* agent.ministere.tchap.gouv.fr`
"""
