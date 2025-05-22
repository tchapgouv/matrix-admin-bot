import json
import secrets
import string
from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class ResetPasswordCommand(UserRelatedCommand):
    KEYWORD = "reset_password"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing ResetPasswordCommand",
            room_id=room.room_id,
            message_id=message.event_id,
        )
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.failed_user_ids: list[str] = []

    async def reset_password(
        self, user_id: str, password: str, *, logout_devices: bool = True
    ) -> bool:
        logger.debug(
            "Resetting password for user",
            user_id=user_id,
            logout_devices=logout_devices,
        )
        if get_server_name(user_id) != self.server_name:
            logger.debug("User is not on local server, skipping", user_id=user_id)
            return True

        logger.debug("Getting user devices", user_id=user_id)
        resp = await self.matrix_client.send(
            "GET",
            f"/_synapse/admin/v2/users/{user_id}/devices",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
        )

        self.json_report.setdefault(user_id, {})

        if resp.ok:
            json_body = await resp.json()
            self.json_report[user_id]["devices"] = json_body.get("devices", [])
            logger.debug(
                "Retrieved user devices",
                user_id=user_id,
                device_count=len(self.json_report[user_id]["devices"]),
            )
        else:
            logger.warning(
                "Failed to get user devices", user_id=user_id, status=resp.status
            )

        logger.debug("Sending password reset request", user_id=user_id)
        resp = await self.matrix_client.send(
            "POST",
            f"/_synapse/admin/v1/reset_password/{user_id}",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            data=json.dumps(
                {
                    "new_password": password,
                    "logout_devices": logout_devices,
                }
            ),
        )
        if not resp.ok:
            json_body = await resp.json()
            self.json_report[user_id].update(json_body)
            self.failed_user_ids.append(user_id)
            logger.error(
                "Failed to reset password",
                user_id=user_id,
                status=resp.status,
                error=json_body,
            )
            return False

        logger.info("Successfully reset password", user_id=user_id)
        return True

    @override
    async def simple_execute(self) -> bool:
        logger.debug("Executing password reset command", user_ids=self.user_ids)

        def randomword(length: int) -> str:
            characters = string.ascii_lowercase + string.digits
            return "".join(secrets.choice(characters) for _ in range(length))

        for user_id in self.user_ids:
            logger.debug("Generating new password for user", user_id=user_id)
            new_password = randomword(32)
            await self.reset_password(user_id, new_password)

        if self.json_report:
            logger.debug("Preparing report", report=self.json_report)
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if self.failed_user_ids:
            logger.warning(
                "Some password resets failed", failed_users=self.failed_user_ids
            )
            text = "\n".join(
                [
                    "Couldn't reset the password of the following users:",
                    "",
                    *[f"- {user_id}" for user_id in self.failed_user_ids],
                ]
            )
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        success = not self.failed_user_ids
        logger.debug("Password reset command completed", success=success)
        return success

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to reset password of the following users:",
                "",
                *[f"- {user_id}" for user_id in self.user_ids],
                "",
                "⚠⚠ This will also log-out all of their devices!",
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!reset_password <user1> [user2] ...`

**Purpose**:
Resets a user's password to a new randomly generated one.

**Effects**:
- Logs out all devices currently logged into the account
- Displays the new password in the JSON report of the command

**Examples**:
- `!reset_password @user:example.com`
- `!reset_password @user1:example.com @user2:example.com`
"""
