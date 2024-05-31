from typing import Optional

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from typing_extensions import override

from matrix_admin_bot.commands.reset_password import ResetPasswordCommand
from matrix_admin_bot.totpbot import Command, TOTPBot

COMMANDS: list[type[Command]] = [ResetPasswordCommand]


class AdminBotConfig(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml")

    homeserver: str = "http://localhost:8008"
    bot_username: str = ""
    bot_password: str = ""
    totps: dict[str, str] = {}
    coordinator: Optional[str] = None

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


def main():
    config = AdminBotConfig()
    bot = TOTPBot(
        config.homeserver,
        config.bot_username,
        config.bot_password,
        COMMANDS,
        config.totps,
        config.coordinator,
    )
    bot.run()
