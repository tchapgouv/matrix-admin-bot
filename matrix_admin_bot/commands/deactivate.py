import json
from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class DeactivateCommand(UserRelatedCommand):
    KEYWORD = "deactivate"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing DeactivateCommand",
            room_id=room.room_id,
            message_id=message.event_id,
        )
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.failed_user_ids: list[str] = []

    async def deactivate_user(self, user_id: str) -> bool:
        logger.debug("Deactivating user", user_id=user_id)
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

        # TODO handle unknown user here and return
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

        logger.debug("Sending deactivation request", user_id=user_id)
        resp = await self.matrix_client.send(
            "POST",
            f"/_synapse/admin/v1/deactivate/{user_id}",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            data=json.dumps({"erase": False}),
        )
        if not resp.ok:
            json_body = await resp.json()
            self.json_report[user_id].update(json_body)
            self.failed_user_ids.append(user_id)
            logger.error(
                "Failed to deactivate user",
                user_id=user_id,
                status=resp.status,
                error=json_body,
            )
            return False

        logger.info("Successfully deactivated user", user_id=user_id)
        return True

    @override
    async def simple_execute(self) -> bool:
        logger.debug("Executing deactivate command", user_ids=self.user_ids)
        for user_id in self.user_ids:
            await self.deactivate_user(user_id)

        if self.json_report:
            logger.debug("Preparing report", report=self.json_report)
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if self.failed_user_ids:
            logger.warning(
                "Some deactivations failed", failed_users=self.failed_user_ids
            )
            text = "\n".join(
                [
                    "Couldn't deactivate the following users:",
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
        logger.debug("Deactivate command completed", success=success)
        return success

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to deactivate the following users:",
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
`!deactivate <user1> [user2] ...`

**Purpose**:
Deactivates Matrix accounts.

**Effects**:
- Logs out all devices currently logged into the account
- Prevents the user from logging in again byt removing their access token and password
- Remove the user from all rooms
- The user ID remains reserved and cannot be registered by someone else

**Examples**:
- `!deactivate @user:example.com`
- `!deactivate @user1:example.com user2@example.com`

**Notes**:
- This action cannot be easily undone
"""
