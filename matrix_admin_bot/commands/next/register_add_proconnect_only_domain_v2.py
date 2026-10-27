from collections.abc import Mapping
from typing import Any, override

from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.commands.next.register_proconnect_only_domain import (
    POLICY_DATA_KEY,
    RegisterProconnectOnlyDomainCommand,
)


class RegisterAddProconnectOnlyDomainCommandV2(RegisterProconnectOnlyDomainCommand):
    KEYWORD = "register_add_proconnect_only_domain"

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
        if domain in domains:
            return None
        return [*domains, domain]

    @override
    def no_change_message(self, domain: str, domains: list[str]) -> str:
        return "\n".join(
            [
                (
                    f"The domain `{domain}` is already in the "
                    f"`{POLICY_DATA_KEY}` list of homeserver "
                    f"`{self.server_name}`."
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
                    f"The domain `{domain}` has been **added** to the "
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
                    f"You are about to **add** the domain `{self.domain}` to "
                    f"the `{POLICY_DATA_KEY}` list of homeserver "
                    f"`{self.server_name}`."
                ),
                "",
                (
                    "Users with an email on this domain will only be able to "
                    "register via ProConnect."
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
Add a domain to the `{POLICY_DATA_KEY}` list of the MAS policy data.
Users with an email on a listed domain can only register via ProConnect:
the "continue with email" button is hidden on the register page.

**Parameters**:
- `<domain_regexp>`: a regexp matched (full match, lowercased) against
  the email domain. Escape the dots: `ac-versailles\\.fr`. Use `.*` to
  force all the domains of the homeserver.
- `[homeserver]`: optional homeserver server name. By default the
  homeserver in charge of the email domain is guessed from the identity
  server and only the bot of this homeserver executes the command, on
  its own MAS. When given, this homeserver is targeted explicitly,
  without querying the identity server: required for regexps the
  identity server cannot classify, such as `.*`.

**Examples**:
- `!{self.KEYWORD} ac-versailles\\.fr`
- `!{self.KEYWORD} .* agent.ministere.tchap.gouv.fr`
"""
