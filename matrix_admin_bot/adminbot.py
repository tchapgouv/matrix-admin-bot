from matrix_bot.bot import bot_lib_config
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from typing_extensions import override

from matrix_admin_bot.commands.reset_password import ResetPasswordCommand
from matrix_admin_bot.commands.server_notice import ServerNoticeCommand
from matrix_command_bot.command import ICommand
from matrix_command_bot.commandbot import CommandBot
from matrix_command_bot.validation.validators.totp import TOTPValidator

COMMANDS: list[type[ICommand]] = [ResetPasswordCommand, ServerNoticeCommand]


class AdminBotConfig(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml")

    homeserver: str = "http://localhost:8008"
    bot_username: str = ""
    bot_password: str = ""
    allowed_room_ids: list[str] = []
    totps: dict[str, str] = {}
    is_coordinator: bool = True

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
        return (TomlConfigSettingsSource(settings_cls),)


def main() -> None:
    config = AdminBotConfig()
    bot_lib_config.allowed_room_ids = config.allowed_room_ids
    bot = CommandBot(
        homeserver=config.homeserver,
        username=config.bot_username,
        password=config.bot_password,
        commands=COMMANDS,
        is_coordinator=config.is_coordinator,
        secure_validator=TOTPValidator(config.totps),
    )
    bot.run()


if __name__ == "__main__":
    main()
