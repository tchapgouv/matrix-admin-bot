import logging
from typing import Any

from matrix_bot.bot import bot_lib_config
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

logger = logging.getLogger(__name__)

COMMANDS: list[type[ICommand]] = [
    ServerNoticeCommand,
    ResetPasswordCommand,
    AccountValidityCommand,
    DeactivateCommand,
]


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
        logger.warning(config.roles)
        for role_name, role_model in config.roles.items():
            logger.warning("role ", role_name, role_model)
            allowed_commands: list[type[ICommand]] = []
            for allowed_command_str in role_model.allowed_commands:
                allowed_cmd = commands_dict.get(allowed_command_str)
                if allowed_cmd:
                    allowed_commands.append(allowed_cmd)
            logger.warning("allowed commands ", allowed_commands)

            role = Role(role_name, role_model.all_commands, allowed_commands)

            for user_id in role_model.user_ids:
                logger.warning("user_id ", user_id)
                roles.get(user_id, []).append(role)
        logger.warning(roles)
        super().__init__(
            homeserver=config.homeserver,
            username=config.bot_username,
            password=config.bot_password,
            commands=COMMANDS,
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
