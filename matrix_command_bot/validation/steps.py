import structlog
from nio import RoomMessage
from typing_extensions import override

from matrix_command_bot.command import ICommand
from matrix_command_bot.step import CommandAction, ICommandStep
from matrix_command_bot.step.reaction_steps import ReactionCommandState
from matrix_command_bot.util import set_status_reaction
from matrix_command_bot.validation import IValidator

logger = structlog.getLogger(__name__)


class ValidateStep(ICommandStep):
    def __init__(
        self,
        command: ICommand,
        state: ReactionCommandState,
        validator: IValidator,
        message: str | None = None,
    ) -> None:
        super().__init__(command)
        self.validator = validator
        self.prompting_done = False
        self.message = message
        self.state = state
        logger.debug(
            "Initialized ValidateStep",
            command=type(command).__name__,
            validator=type(validator).__name__,
        )

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        logger.debug(
            "ValidateStep.execute called",
            command=type(self.command).__name__,
            validator=type(self.validator).__name__,
        )
        if not self.prompting_done:
            await self.send_prompt()
            self.prompting_done = True

        # It should be ignored since it doesn't come from the original command sender
        # TODO check against SingleUserCommand
        if reply and self.command.message.sender != reply.sender:
            logger.debug(
                "Ignoring reply from non-sender",
                reply_sender=reply.sender,
                command_sender=self.command.message.sender,
            )
            res = False
        else:
            res = await self.validator.validate(reply, self.command)

        return (
            True,
            CommandAction.CONTINUE if res else CommandAction.WAIT_FOR_NEXT_REPLY,
        )

    async def send_prompt(self) -> None:
        logger.debug(
            "ValidateStep.send_prompt called",
            command=type(self.command).__name__,
            validator=type(self.validator).__name__,
        )
        if self.command.extra_config.get("is_coordinator", True):
            confirm_text = self.validator.prompt if self.validator.prompt else ""
            if confirm_text:
                message = self.message if self.message else ""
                if message:
                    confirm_text = f"{message}\n\n" + confirm_text

                await self.command.matrix_client.send_markdown_message(
                    self.command.room.room_id,
                    confirm_text,
                    reply_to=self.command.message.event_id,
                    thread_root=self.command.message.event_id,
                )

            self.state.current_reaction_event_id = await set_status_reaction(
                self.command,
                self.validator.reaction,
                self.state.current_reaction_event_id,
            )
