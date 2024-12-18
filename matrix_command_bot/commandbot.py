from dataclasses import dataclass, field
from typing import Any

import cachetools
import structlog
from matrix_bot.bot import MatrixBot
from matrix_bot.eventparser import EventNotConcerned
from nio import MatrixRoom, RoomMessage
import asyncio

from matrix_command_bot.command import ICommand

logger = structlog.getLogger(__name__)


@dataclass
class Role:
    name: str
    all_commands: bool = False
    allowed_commands: list[type[ICommand]] = field(default_factory=list)


class CommandBot(MatrixBot):
    def __init__(
        self,
        *,
        homeserver: str,
        username: str,
        password: str,
        commands: list[type[ICommand]],
        roles: dict[str, list[Role]] | None = None,
        **extra_config: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(homeserver, username, password)
        self.commands = commands
        self.roles = roles
        self.extra_config = {}
        if extra_config:
            self.extra_config = extra_config

        self.recent_events_cache: cachetools.TTLCache[str, RoomMessage] = (
            cachetools.TTLCache(maxsize=5120, ttl=24 * 60 * 60)
        )
        self.commands_cache: cachetools.TTLCache[str, ICommand] = cachetools.TTLCache(
            maxsize=5120, ttl=24 * 60 * 60
        )

        self.callbacks.register_on_message_event(self.store_event_in_cache)
        self.callbacks.register_on_message_event(self.handle_events)

    async def store_event_in_cache(
        self,
        _room: MatrixRoom,
        message: RoomMessage,
    ) -> None:
        self.recent_events_cache[message.event_id] = message

    def get_replied_event(self, message: RoomMessage) -> RoomMessage | None:
        return self.recent_events_cache.get(
            message.source.get("content", {})
            .get("m.relates_to", {})
            .get("m.in_reply_to", {})
            .get("event_id")
        )

    def get_related_command(self, message: RoomMessage) -> ICommand | None:
        content = message.source.get("content", {})
        if not content:
            return None

        # let's check if we have a thread root message and if it is a command
        if content.get("m.relates_to", {}).get("rel_type") == "m.thread":
            command = self.commands_cache.get(
                content.get("m.relates_to", {}).get("event_id")
            )
            if command:
                return command

        # no thread here, let's check the reply chain for a command to validate
        replied_event = message
        while replied_event:
            replied_event = self.get_replied_event(replied_event)
            if replied_event:
                command = self.commands_cache.get(replied_event.event_id)
                if command:
                    return command

        return None

    def get_replaced_event(self, message: RoomMessage) -> RoomMessage | None:
        relates_to_payload = message.source.get("content", {}).get("m.relates_to", {})
        if relates_to_payload.get("rel_type", "") == "m.replace":
            replace_event_id = relates_to_payload.get("event_id", None)
            if replace_event_id:
                return self.recent_events_cache.get(replace_event_id)
        return None

    async def handle_events(
        self,
        room: MatrixRoom,
        message: RoomMessage,
    ) -> None:
        replaced_event = self.get_replaced_event(message)
        if replaced_event:
            related_command = self.get_related_command(replaced_event)
            if related_command:
                new_content = message.source.get("content", {}).get("m.new_content")
                logger.debug(
                    "A message related to a command has been replaced",
                    new_content=new_content,
                    related_command=related_command,
                    replaced_event=replaced_event,
                )
                await related_command.replace_received(new_content, replaced_event)
                return
        else:
            related_command = self.get_related_command(message)
            if related_command:
                logger.debug(
                    "A reply to a command has been received",
                    related_command=related_command,
                    reply=message,
                )
                await related_command.reply_received(message)
                return

        for command_type in self.commands:
            try:
                command = command_type(
                    room, message, self.matrix_client, self.extra_config
                )
                if await self.can_execute(command):
                    self.commands_cache[message.event_id] = command
                    # Run the command in a separate task so it doesn't block the event loop
                    asyncio.create_task(command.execute(), name=f"ExecuteCommand-{command}")
                    break
            except EventNotConcerned:
                pass
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Unexpected exception when trying to parse a message as %s",
                    command_type.__name__,
                    e=e,
                    message=message,
                )

    async def can_execute(self, command: ICommand) -> bool:
        if not self.roles:
            return True
        user_roles = self.roles.get(command.message.sender, [])
        for role in user_roles:
            if role.all_commands or command.__class__ in role.allowed_commands:
                return True
        return False
