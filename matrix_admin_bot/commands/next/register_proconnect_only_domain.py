import re
from abc import abstractmethod
from collections.abc import Mapping
from typing import Any, override

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot import InteractiveValidatedCommand
from matrix_admin_bot.admin_client import AdminClient
from matrix_command_bot.command import ICommand

logger = structlog.getLogger(__name__)

# Key of the ProConnect-only domain regexes in the MAS policy data, evaluated
# by the `register/proconnect_only` policy entrypoint.
POLICY_DATA_KEY = "register_proconnect_only_domains"

# Regex features not supported by the Rego regex engine (RE2): accepting them
# would make the policy evaluation fail on the MAS side.
UNSUPPORTED_REGEX = re.compile(r"\(\?[=!<>]|\(\?P=|\\[1-9]")

# Local part of the dummy email used to query the identity server: it
# classifies emails by domain, so any local part works.
PROBE_EMAIL_LOCALPART = "tchap.bot.probe"


def probe_email(domain_regexp: str) -> str:
    """Build a dummy email on the plain domain to query the identity server.

    The identity server classifies emails by domain: backslashes are
    stripped from the domain regexp so that `ac-versailles\\.fr` probes
    `ac-versailles.fr`.
    """
    return f"{PROBE_EMAIL_LOCALPART}@{domain_regexp.replace('\\', '')}"


async def reply_markdown_in_thread(command: ICommand, text: str) -> None:
    """Reply to the command message in its thread."""
    await command.matrix_client.send_markdown_message(
        command.room.room_id,
        text,
        reply_to=command.message.event_id,
        thread_root=command.message.event_id,
    )


async def send_command_error(command: ICommand, text: str) -> None:
    """Send a command error, only from the coordinator bot.

    All the bots sharing the admin room parse the command: only the
    coordinator reports parsing errors to avoid duplicated messages.
    """
    if command.extra_config.get("is_coordinator", True):
        await reply_markdown_in_thread(command, text)


class RegisterProconnectOnlyDomainCommand(InteractiveValidatedCommand):
    """Base class to add or remove a ProConnect-only domain in the MAS
    policy data.

    The homeserver in charge of the email domain is guessed from the
    identity server (as `is_email_valid` does): only the bot of this
    homeserver executes the command, on its own MAS. The other bots
    sharing the admin room stay silent.
    """

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        keyword: str,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, keyword, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.domain: str | None = None

    @abstractmethod
    def update_domains(self, domain: str, domains: list[str]) -> list[str] | None:
        """Return the updated domain list, or None when no change is needed."""

    @abstractmethod
    def no_change_message(self, domain: str, domains: list[str]) -> str:
        """Return the message sent when no change is needed."""

    @abstractmethod
    def success_message(self, domain: str, new_domains: list[str]) -> str:
        """Return the message sent after a successful update."""

    @override
    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        args = self.command_text.split()
        if len(args) != 1:
            await send_command_error(
                self, f"Invalid syntax. Usage: `!{self.keyword} <domain_regexp>`"
            )
            return True

        domain = args[0]
        try:
            re.compile(domain)
        except re.error:
            await send_command_error(self, f"Invalid domain regexp: `{domain}`.")
            return True
        if UNSUPPORTED_REGEX.search(domain):
            await send_command_error(
                self,
                f"The domain regexp `{domain}` uses features not supported "
                "by the policy regex engine (lookaround or backreference).",
            )
            return True

        self.domain = domain

        return await super().execute()

    @override
    async def should_execute(self) -> bool:
        # Guess from the identity server which homeserver is in charge of
        # this email domain: execute only if it is this bot's homeserver
        # (same multi-bot filtering as `is_local_user` in
        # UserRelatedCommand). The other bots sharing the admin room stay
        # silent.
        if self.domain is None:
            return False
        homeserver = await self.admin_client.get_homeserver(probe_email(self.domain))
        return homeserver is not None and homeserver == self.server_name

    @override
    async def simple_execute(self) -> bool:
        domain = self.domain
        if domain is None:
            # Should not happen: execute() sets it before running the steps
            return False

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
        new_domains = self.update_domains(domain, domains)
        if new_domains is None:
            await reply_markdown_in_thread(
                self, self.no_change_message(domain, domains)
            )
            return True

        policy_data[POLICY_DATA_KEY] = new_domains
        if not await self.admin_client.set_policy_data(policy_data):
            await reply_markdown_in_thread(
                self, "Failed to update the policy data on MAS."
            )
            return False

        await reply_markdown_in_thread(self, self.success_message(domain, new_domains))
        return True
