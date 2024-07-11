from nio import RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import CommandAction, ICommandStep
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
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if self.command.extra_config.get("is_coordinator", True):
            confirm_text = self.validator.prompt if self.validator.prompt else ""
            if confirm_text:
                message = self.message if self.message else ""
                if message:
                    confirm_text += f"\n\n{message}"

                await self.command.matrix_client.send_markdown_message(
                    self.command.room.room_id,
                    confirm_text,
                    reply_to=self.command.message.event_id,
                    thread_root=self.command.message.event_id,
                )

        await self.command.set_status_reaction(self.validator.reaction)

        return True, CommandAction.CONTINUE


class ValidateStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        validator: IValidator,
    ) -> None:
        super().__init__(command)
        self.validator = validator

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if self.validator.prompt and not reply:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        # It should be ignored since it doesn't come from the original command sender
        if reply and self.command.message.sender != reply.sender:
            return True, CommandAction.WAIT_FOR_NEXT_REPLY

        res = await self.validator.validate(reply, self.command)
        return (
            True,
            CommandAction.CONTINUE if res else CommandAction.WAIT_FOR_NEXT_REPLY,
        )
