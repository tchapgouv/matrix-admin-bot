import re
from abc import ABC, abstractmethod
from typing import Optional

import cachetools
from matrix_bot.bot import MatrixBot
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import EventNotConcerned
from nio import MatrixRoom, RoomMessage, RoomMessageText
from pyotp import TOTP

REMOVE_REPLY_REGEX = re.compile("<mx-reply>.*</mx-reply>(.*)", re.MULTILINE | re.DOTALL)


class Command(ABC):
    def __init__(
        self, room: MatrixRoom, message: RoomMessage, matrix_client: MatrixClient
    ) -> None:
        self.room = room
        self.message = message
        self.matrix_client = matrix_client
        self.current_status_reaction = None

    async def set_status_reaction(self, key: Optional[str]) -> None:
        if self.current_status_reaction:
            await self.matrix_client.room_redact(
                self.room.room_id, self.current_status_reaction
            )
        if key:
            self.current_status_reaction = await self.matrix_client.send_reaction(
                self.room.room_id, self.message, key
            )

    async def send_result(self) -> None:
        pass

    @abstractmethod
    async def execute(self) -> bool: ...


class CommandToValidate(Command):
    TOTP_PROMPT = (
        "Please reply to this message with an authentication code"
        " to validate the action."
    )

    async def send_validation_message(self) -> None:
        pass


class TOTPBot(MatrixBot):
    def __init__(
        self,
        homeserver: str,
        username: str,
        password: str,
        commands: list[type[Command]],
        totps: dict[str, str],
        coordinator: Optional[str],
    ):
        super().__init__(homeserver, username, password)
        self.commands = commands
        self.coordinator = coordinator

        self.totps = {user_id: TOTP(totp_seed) for user_id, totp_seed in totps.items()}

        self.recent_events_cache: cachetools.TTLCache[str, RoomMessage] = (
            cachetools.TTLCache(maxsize=5120, ttl=24 * 60 * 60)
        )
        self.commands_cache: cachetools.TTLCache[str, Command] = cachetools.TTLCache(
            maxsize=5120, ttl=24 * 60 * 60
        )

        self.callbacks.register_on_message_event(self.store_event_in_cache)
        self.callbacks.register_on_message_event(self.validate_totp_and_execute)
        self.callbacks.register_on_message_event(self.handle_commands)

    async def store_event_in_cache(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ):
        self.recent_events_cache[message.event_id] = message

    @staticmethod
    def extract_totp_code(message: RoomMessageText) -> Optional[str]:
        body = message.body
        if message.formatted_body:
            m = REMOVE_REPLY_REGEX.match(message.formatted_body)
            if m:
                body = m.group(1)

        body = body.strip().replace(" ", "")

        if not (len(body) == 6 and body.isdigit()):
            return None

        return body

    async def validate_totp(
        self,
        room: MatrixRoom,
        message: RoomMessageText,
        command_message_id: str,
    ):
        error_msg = None

        totp_code = self.extract_totp_code(message)
        if totp_code:
            totp_checker = self.totps.get(message.sender)
            if not totp_checker:
                error_msg = "You are not allowed to execute admin commands, sorry."
            elif not totp_checker.verify(totp_code):
                error_msg = "Wrong authentication code."
        else:
            error_msg = (
                "Couldnt parse the authentication code, it should be a 6 digits code."
            )
        if error_msg is not None:
            await self.matrix_client.send_text_message(
                room.room_id,
                error_msg,
                reply_to=message.event_id,
                thread_root=command_message_id,
            )
            return False

        return True

    def get_replied_event(self, message: RoomMessage):
        return self.recent_events_cache.get(
            message.source.get("content", {})
            .get("m.relates_to", {})
            .get("m.in_reply_to", {})
            .get("event_id")
        )

    async def get_related_command_to_validate(
        self, message: RoomMessage
    ) -> Optional[CommandToValidate]:
        content = message.source.get("content", {})
        if not content:
            return None

        # let's check if we have a thread root message and if it is a command
        command_to_validate: Optional[CommandToValidate] = None
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

    async def validate_totp_and_execute(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ):
        if not isinstance(message, RoomMessageText):
            return

        content = message.source.get("content", {})
        if not content:
            return

        # let's check if we have a thread root message and if it is a command
        command_to_validate: Optional[
            CommandToValidate
        ] = await self.get_related_command_to_validate(message)

        if not command_to_validate:
            return

        # the validation code should come from the sender of the command
        if command_to_validate.message.sender != message.sender:
            return

        if await self.validate_totp(
            room, message, command_to_validate.message.event_id
        ):
            await self.execute_command(command_to_validate)

    async def execute_command(self, command: Command):
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

    async def handle_commands(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
    ):
        for command_type in self.commands:
            try:
                command = command_type(room, message, matrix_client)
                if isinstance(command, CommandToValidate):
                    self.commands_cache[message.event_id] = command
                    if (
                        not self.coordinator
                        or matrix_client.user_id == self.coordinator
                    ):
                        await command.send_validation_message()
                        await command.set_status_reaction("🔢")
                else:
                    await self.execute_command(command)
                # TODO break or not ?
            except EventNotConcerned:
                pass
