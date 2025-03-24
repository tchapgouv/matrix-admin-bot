from nio import RoomMessage
from typing_extensions import override

from matrix_command_bot.step import (
    CommandAction,
    CommandWithSteps,
    ICommandStep,
)
from matrix_command_bot.util import set_status_reaction


class ReactionCommandState:
    def __init__(self) -> None:
        self.current_reaction_event_id: str | None = None


class ReactionStep(ICommandStep):
    def __init__(
        self,
        command: CommandWithSteps,
        state: ReactionCommandState,
        reaction: str | None,
    ) -> None:
        super().__init__(command)
        self.command = command
        self.state = state
        self.reaction = reaction

    @override
    async def execute(
        self,
        reply: RoomMessage | None = None,
    ) -> tuple[bool, CommandAction]:
        self.state.current_reaction_event_id = await set_status_reaction(
            self.command, self.reaction, self.state.current_reaction_event_id
        )
        return True, CommandAction.CONTINUE


class ResultReactionStep(ReactionStep):
    def __init__(
        self,
        command: CommandWithSteps,
        state: ReactionCommandState,
        success_reaction: str | None = "✅",
        failure_reaction: str | None = "❌",
    ) -> None:
        super().__init__(command, state, None)
        self.success_reaction = success_reaction
        self.failure_reaction = failure_reaction

    @override
    async def execute(
        self,
        reply: RoomMessage | None = None,
    ) -> tuple[bool, CommandAction]:
        self.reaction = (
            self.success_reaction
            if self.command.current_result
            else self.failure_reaction
        )
        return await super().execute(reply)
