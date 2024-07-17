from typing import Any

import cachetools
from matrix_bot.bot import MatrixBot
from matrix_bot.eventparser import EventNotConcerned
from nio import MatrixRoom, RoomMessage

from matrix_command_bot.command import ICommand


class CommandBot(MatrixBot):
    def __init__(
        self,
        *,
        homeserver: str,
        username: str,
        password: str,
        commands: list[type[ICommand]],
        **extra_config: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(homeserver, username, password)
        self.commands = commands
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

    async def get_related_command(self, message: RoomMessage) -> ICommand | None:
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

    async def handle_events(
        self,
        room: MatrixRoom,
        message: RoomMessage,
    ) -> None:
        related_command = await self.get_related_command(message)
        if related_command:
            await related_command.reply_received(message)
            return

        for command_type in self.commands:
            try:
                command = command_type(
                    room, message, self.matrix_client, self.extra_config
                )
                self.commands_cache[message.event_id] = command
                await command.execute()
                # TODO break or not ?
            except EventNotConcerned:
                pass
