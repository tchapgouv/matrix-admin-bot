

import cachetools
import structlog
from matrix_bot.bot import MatrixBot
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import EventNotConcerned, MessageEventParser
from nio import MatrixRoom, RoomMessage

from matrix_admin_bot.command import Command, CommandToValidate

logger = structlog.getLogger(__name__)


class BotHandler(MatrixBot):
    def __init__(
        self,
        *,
        homeserver: str,
        username: str,
        password: str,
        commands: list[type[Command]],
        totps: dict[str, str] | None,
        coordinator: str | None,
    ) -> None:
        super().__init__(homeserver, username, password)
        self.commands = commands
        self.totps = totps
        self.coordinator = coordinator

        self.recent_events_cache: cachetools.TTLCache[str, RoomMessage] = (
            cachetools.TTLCache(maxsize=5120, ttl=24 * 60 * 60)
        )
        self.commands_cache: cachetools.TTLCache[str, Command] = cachetools.TTLCache(
            maxsize=5120, ttl=24 * 60 * 60
        )

        self.callbacks.register_on_message_event(self.store_event_in_cache)
        # self.callbacks.register_on_message_event(self.validate_and_execute)
        self.callbacks.register_on_message_event(self.handle_commands, self.matrix_client)

    async def store_event_in_cache(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ) -> None:
        self.recent_events_cache[message.event_id] = message

    def get_replied_event(self, message: RoomMessage) -> RoomMessage | None:
        return self.recent_events_cache.get(
            message.source.get("content", {})
            .get("m.relates_to", {})
            .get("m.in_reply_to", {})
            .get("event_id")
        )

    async def get_related_command_to_validate(
        self, message: RoomMessage
    ) -> CommandToValidate | None:
        content = message.source.get("content", {})
        if not content:
            return None

        # let's check if we have a thread root message and if it is a command
        command_to_validate: CommandToValidate | None = None
        if content.get("m.relates_to", {}).get("rel_type") == "m.thread":
            command = self.commands_cache.get(
                content.get("m.relates_to", {}).get("event_id")
            )
            if isinstance(command, CommandToValidate):
                return command

        if not command_to_validate:
            # no thread here, let's check the reply chain for a command to validate
            replied_event = message
            while replied_event:
                replied_event = self.get_replied_event(replied_event)
                if replied_event:
                    command = self.commands_cache.get(replied_event.event_id)
                    if isinstance(command, CommandToValidate):
                        return command

        return None

    async def handle_commands(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ) -> None:
        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        try:
            event_parser.do_not_accept_own_message()
        except EventNotConcerned:
            return
        # Existing command
        command = await self.find_existing_command(room, message, matrix_client)
        logger.info(f"existing_command={command}")
        if command:
            await command.process_validator_steps(message)
        else:
            # Is new command
            command = self.create_command(room, message, matrix_client)
            if command:
                logger.info(f"new command={command}")
                await command.process_validator_steps(message)

        if not command:
            logger.info(f"command=No command found for {message}")
            return

        if not command.is_valid():
            logger.info(f"command is not ready")
            return

        await self.execute_command(command)

    async def find_existing_command(self, room, message, matrix_client) -> (
            CommandToValidate | None
        ):
        existing_command_request = await self.get_related_command_to_validate(message)
        return existing_command_request

    def create_command(self, room, message, matrix_client) -> CommandToValidate:
        for command_type in self.commands:
            try:
                if issubclass(command_type, CommandToValidate):
                    command = command_type(room, message, matrix_client, self.totps)
                else:
                    command = command_type(room, message, matrix_client)
                self.commands_cache[message.event_id] = command
                return command
            except EventNotConcerned:
                pass
        return None

    async def execute_command(self, command: Command) -> None:
        await command.set_status_reaction("🚀")
        result_reaction = "❌"
        try:
            res = await command.execute()
            if res:
                result_reaction = "✅"
        except Exception as e:
            print(e)

        await command.set_status_reaction(result_reaction)
        try:
            await command.send_result()
        except Exception as e:
            print(e)