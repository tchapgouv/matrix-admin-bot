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

# A JSON value, as found in the MAS policy data
type JSONValue = (
    bool | int | float | str | list[JSONValue] | dict[str, JSONValue] | None
)


class PolicyValueError(Exception):
    """Raised by update_value when the current value cannot be updated."""


# Regex features not supported by the Rego regex engine (RE2): accepting them
# would make the policy evaluation fail on the MAS side.
UNSUPPORTED_REGEX = re.compile(r"\(\?[=!<>]|\(\?P=|\\[1-9]")


def unsupported_regex_error(value: str) -> str | None:
    """Return an error message when the value uses regex features not
    supported by the policy regex engine (RE2), None when it is safe.

    Several policies evaluate their policy data values as regexes with
    the RE2 engine, e.g. `register_proconnect_only_domains` or
    `registration.allowed_usernames`. A regex using features unsupported
    by RE2 (lookaround or backreference) would make the policy evaluation
    fail on the MAS side, e.g. breaking the register page of the whole
    homeserver. Plain strings never use these features, so non-regex
    values are accepted as well.
    """
    if UNSUPPORTED_REGEX.search(value):
        return (
            f"The value `{value}` uses regex features not supported "
            "by the policy regex engine (lookaround or backreference)."
        )
    return None


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


def parse_policy_key(policy_key: str) -> list[str] | None:
    """Split a dotted policy data key path into its segments.

    For example `registration.allowed_usernames` is split into
    `["registration", "allowed_usernames"]`. Return None when the path is
    invalid (empty key or empty segment).
    """
    segments = policy_key.split(".")
    if not policy_key or any(not segment for segment in segments):
        return None
    return segments


def get_at_path(data: dict[str, JSONValue], path: list[str]) -> JSONValue:
    """Return the value at the dotted key path, None when it is not set."""
    current: JSONValue = data
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current


def set_at_path(data: dict[str, JSONValue], path: list[str], value: JSONValue) -> None:
    """Set the value at the dotted key path.

    The intermediate objects are created when missing so that nested keys
    such as `registration.allowed_usernames` can be set in one go; the
    sibling keys are preserved.
    """
    current: dict[str, JSONValue] = data
    for segment in path[:-1]:
        child = current.get(segment)
        if not isinstance(child, dict):
            child = {}
            current[segment] = child
        current = child
    current[path[-1]] = value


class PolicyDataCommand(InteractiveValidatedCommand):
    """Base class to change any key of the MAS policy data.

    The policy data is a JSON document evaluated by the MAS policies: its
    keys are referenced from the policies with a dotted path, e.g.
    `registration.allowed_usernames` or
    `register_proconnect_only_domains`.

    The target homeserver is a required command parameter: only the bot of
    this homeserver executes the command, on its own MAS. The other bots
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
        self.homeserver: str | None = None
        # Segments of the dotted policy data key path, e.g.
        # "registration" + "allowed_usernames" for
        # "registration.allowed_usernames"
        self.policy_key: list[str] = []

    @property
    def policy_key_str(self) -> str:
        """The dotted policy data key path, e.g. `registration.allowed_usernames`."""
        return ".".join(self.policy_key)

    @abstractmethod
    def parse_args(self, args: list[str]) -> str | None:
        """Parse the command arguments.

        Set the policy_key and homeserver attributes (and any
        command-specific value attribute). Return an error message when
        the arguments are invalid, or None when they are valid.
        """

    @abstractmethod
    def update_value(self, current: JSONValue) -> tuple[bool, JSONValue]:
        """Return (changed, new_value) for the policy key.

        `current` is the current value at the policy key, None when it is
        not set. Raise PolicyValueError when the current value cannot be
        updated as requested.
        """

    @abstractmethod
    def no_change_message(self, current: JSONValue) -> str:
        """Return the message sent when no change is needed."""

    @abstractmethod
    def success_message(self, new_value: JSONValue) -> str:
        """Return the message sent after a successful update."""

    @override
    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        error = self.parse_args(self.command_text.split())
        if error is not None:
            await send_command_error(self, error)
            return True

        return await super().execute()

    @override
    async def should_execute(self) -> bool:
        # Only the bot of the target homeserver executes the command
        # (same multi-bot filtering as `is_local_user` in
        # UserRelatedCommand). The other bots sharing the admin room stay
        # silent.
        return self.homeserver == self.server_name

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

        current = get_at_path(policy_data, self.policy_key)
        try:
            changed, new_value = self.update_value(current)
        except PolicyValueError as error:
            await reply_markdown_in_thread(self, str(error))
            return True
        if not changed:
            await reply_markdown_in_thread(self, self.no_change_message(current))
            return True

        set_at_path(policy_data, self.policy_key, new_value)
        if not await self.admin_client.set_policy_data(policy_data):
            await reply_markdown_in_thread(
                self, "Failed to update the policy data on MAS."
            )
            return False

        await reply_markdown_in_thread(self, self.success_message(new_value))
        return True
