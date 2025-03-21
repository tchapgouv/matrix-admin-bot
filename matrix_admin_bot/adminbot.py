from collections.abc import Mapping
from typing import Any

from matrix_bot.bot import MatrixClient, bot_lib_config
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from typing_extensions import override

from matrix_admin_bot.commands.account_validity import AccountValidityCommand
from matrix_admin_bot.commands.deactivate import DeactivateCommand
from matrix_admin_bot.commands.reset_password import ResetPasswordCommand
from matrix_admin_bot.commands.server_notice import ServerNoticeCommand
from matrix_command_bot.command import ICommand
from matrix_command_bot.commandbot import CommandBot, Role
from matrix_command_bot.validation.validators.totp import TOTPValidator

COMMANDS: list[type[ICommand]] = [
    ServerNoticeCommand,
    ResetPasswordCommand,
    AccountValidityCommand,
    DeactivateCommand,
]


class HelpCommand(ICommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        event_parser.command("help")

    async def execute(self) -> bool:
        if self.extra_config.get("is_coordinator", True):
            help_message = (
                "Here are the available commands, "
                "please use `!<command> help` to get "
                "more information about a specific command:\n\n"
            )
            for command in COMMANDS:
                keyword = getattr(command, "KEYWORD", None)
                if keyword:
                    help_message += f"- **!{keyword}**\n"
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                help_message,
            )
        return True


class RoleModel(BaseModel):
    all_commands: bool = False
    allowed_commands: list[str] = []
    user_ids: list[str] = []


class AdminBotConfig(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml", extra="ignore")

    homeserver: str = "http://localhost:8008"
    bot_username: str = ""
    bot_password: str = ""
    allowed_room_ids: list[str] = []
    totps: dict[str, str] = {}
    is_coordinator: bool = True
    roles: dict[str, RoleModel] = {}

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            TomlConfigSettingsSource(settings_cls),
        )


class AdminBot(CommandBot):
    def __init__(
        self,
        config: AdminBotConfig,
        **extra_config: Any,  # noqa: ANN401
    ) -> None:
        if "secure_validator" not in extra_config:
            extra_config["secure_validator"] = TOTPValidator(config.totps)
        bot_lib_config.allowed_room_ids = config.allowed_room_ids

        roles: dict[str, list[Role]] = {}

        commands_dict = {c.__name__: c for c in COMMANDS}
        for role_name, role_model in config.roles.items():
            allowed_commands: list[type[ICommand]] = []
            for allowed_command_str in role_model.allowed_commands:
                allowed_cmd = commands_dict.get(allowed_command_str)
                if allowed_cmd:
                    allowed_commands.append(allowed_cmd)

            role = Role(role_name, role_model.all_commands, allowed_commands)

            for user_id in role_model.user_ids:
                roles.setdefault(user_id, []).append(role)
        super().__init__(
            homeserver=config.homeserver,
            username=config.bot_username,
            password=config.bot_password,
            commands=[*COMMANDS, HelpCommand],
            roles=roles,
            is_coordinator=config.is_coordinator,
            **extra_config,
        )


def main() -> None:
    config = AdminBotConfig()
    bot_lib_config.allowed_room_ids = config.allowed_room_ids
    bot = AdminBot(config)
    bot.run()


if __name__ == "__main__":
    main()
