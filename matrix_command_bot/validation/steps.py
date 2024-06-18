from nio import RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import ICommandStep
from matrix_command_bot.validation import IValidator


class ConfirmStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        validator: IValidator,
    ) -> None:
        super().__init__(command)
        self.validator = validator

    @property
    def message(self) -> str | None:
        return None

    @override
    async def execute(self, reply: RoomMessage | None = None) -> bool:
        message = self.message if self.message else ""
        validation_prompt = self.validator.prompt if self.validator.prompt else ""
        if message and validation_prompt:
            message += "\n\n"
        message += validation_prompt

        if message:
            await self.command.matrix_client.send_markdown_message(
                self.command.room.room_id,
                message,
                reply_to=self.command.message.event_id,
                thread_root=self.command.message.event_id,
            )

        await self.command.set_status_reaction(self.validator.reaction)

        return True


class ValidateStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        validator: IValidator,
    ) -> None:
        super().__init__(command)
        self.validator = validator

    @override
    async def execute(self, reply: RoomMessage | None = None) -> bool:
        return await self.validator.validate(reply, self.command)

    @override
    def wait_for_next_reply(self, current_reply: RoomMessage | None) -> bool:
        if not self.validator.prompt:
            return False
        return current_reply is None
