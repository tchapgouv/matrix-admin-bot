from typing_extensions import override

from matrix_command_bot.step import CommandWithSteps, ICommandStep


class ResultReactionStep(ICommandStep):
    def __init__(
        self,
        command: CommandWithSteps,
        success_reaction: str | None = "✅",
        failure_reaction: str | None = "❌",
    ) -> None:
        super().__init__(command)
        self.command = command
        self.success_reaction = success_reaction
        self.failure_reaction = failure_reaction

    @property
    @override
    def status_reaction(self) -> str | None:
        if self.command.current_result:
            return self.success_reaction
        return self.failure_reaction


class ReactionStep(ICommandStep):
    def __init__(
        self,
        command: CommandWithSteps,
        reaction: str | None,
    ) -> None:
        super().__init__(command)
        self.command = command
        self.reaction = reaction

    @property
    @override
    def status_reaction(self) -> str | None:
        return self.reaction
