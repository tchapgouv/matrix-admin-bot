import secrets
import string
from collections.abc import Mapping
from typing import Any

import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.util import get_localpart_from_id, get_server_name

logger = structlog.getLogger(__name__)


class ResetPasswordCommandV2(UserRelatedCommand):
    KEYWORD = "reset_password"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.failed_user_ids: list[str] = []

    async def reset_password(self, user_id: str, password: str) -> bool:
        if get_server_name(user_id) != self.server_name:
            return True

        # Initialize report for user_id
        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        # Get devices from the user in Synapse
        await self.get_devices_from_synapse(user_id)

        # Get the user from the MAS with its localpart
        mas_user_id = await self.get_mas_user_id(user_id)
        if mas_user_id is None:
            return False

        # Get all compat-sessions in MAS
        await self.get_compat_sessions(mas_user_id, user_id)

        # Get all user-sessions in MAS
        await self.get_user_sessions(mas_user_id, user_id)

        # Get all oauth2-sessions
        await self.get_oauth2_sessions(mas_user_id, user_id)

        # Reset the password within the MAS
        set_password_success = await self.set_password(mas_user_id, password, user_id)
        if not set_password_success:
            return False

        # Kill all sessions
        return await self.kill_all_sessions(mas_user_id, user_id)

    async def kill_all_sessions(self, mas_user_id: str, user_id: str) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/kill-sessions"
        resp = self.admin_client.send_to_mas("POST", endpoint=endpoint)
        json_body = resp.json()
        if not resp.ok:
            error = f"Cannot kill all sessions in MAS {user_id}"
            self.json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            self.failed_user_ids.append(user_id)
            return False
        return True

    async def set_password(self, mas_user_id: str, password: str, user_id: str) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/set-password"
        data = {"password": password, "skip_password_check": True}
        resp = self.admin_client.send_to_mas("POST", endpoint=endpoint, json=data)
        if not resp.ok:
            json_body = resp.json()
            error = f"Cannot get reset password in MAS for {user_id}"
            self.json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            self.failed_user_ids.append(user_id)
            return False
        return True

    async def get_oauth2_sessions(self, mas_user_id: str, user_id: str) -> None:
        params = {"filter[user]": mas_user_id, "filter[status]": "active"}
        endpoint = "/api/admin/v1/oauth2-sessions"
        resp = self.admin_client.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = resp.json()
        if resp.ok:
            count = json_body["meta"]["count"]
            if count > 0:
                sessions = json_body["data"]
                self.json_report[user_id]["oauth2-sessions"] = sessions
                logger.debug(
                    "OAuth2-Sessions : %s", self.json_report[user_id]["oauth2-sessions"]
                )
        else:
            error = f"Cannot get oauth2 session in MAS for {user_id}"
            self.json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            self.failed_user_ids.append(user_id)

    async def get_user_sessions(self, mas_user_id: str, user_id: str) -> None:
        params = {"filter[user]": mas_user_id, "filter[status]": "active"}
        endpoint = "/api/admin/v1/user-sessions"
        resp = self.admin_client.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = resp.json()
        if resp.ok:
            count = json_body["meta"]["count"]
            if count > 0:
                sessions = json_body["data"]
                self.json_report[user_id]["user-sessions"] = sessions
                logger.debug(
                    "User-Sessions : %s", self.json_report[user_id]["user-sessions"]
                )
        else:
            error = f"Cannot get user session in MAS for {user_id}"
            self.json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            self.failed_user_ids.append(user_id)

    async def get_compat_sessions(self, mas_user_id: str, user_id: str) -> None:
        params = {"filter[user]": mas_user_id, "filter[status]": "active"}
        endpoint = "/api/admin/v1/compat-sessions"
        resp = self.admin_client.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = resp.json()
        if resp.ok:
            count = json_body["meta"]["count"]
            if count > 0:
                sessions = json_body["data"]
                self.json_report[user_id]["compat-sessions"] = sessions
                logger.debug(
                    "Compat-Sessions : %s", self.json_report[user_id]["compat-sessions"]
                )
        else:
            error = f"Cannot get compat session in MAS from localpart {user_id}"
            self.json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            self.failed_user_ids.append(user_id)

    async def get_mas_user_id(self, user_id: str) -> str | None:
        username = get_localpart_from_id(user_id)
        endpoint = f"/api/admin/v1/users/by-username/{username}"
        resp = self.admin_client.send_to_mas("GET", endpoint=endpoint)
        json_body = resp.json()
        if not resp.ok:
            error = f"Cannot get user in MAS from localpart {user_id}"
            self.json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            self.failed_user_ids.append(user_id)
            return None
        return json_body["data"]["id"]

    async def get_devices_from_synapse(self, user_id: str) -> None:
        endpoint = f"/_synapse/admin/v2/users/{user_id}/devices"
        resp = await self.admin_client.send_to_synapse(
            "GET",
            endpoint=endpoint,
        )
        if resp.ok:
            json_body = await resp.json()
            self.json_report[user_id]["devices"] = json_body.get("devices", [])
            logger.info("Devices : %s", self.json_report[user_id]["devices"])

    @override
    async def simple_execute(self) -> bool:
        def randomword(length: int) -> str:
            characters = string.ascii_lowercase + string.digits
            return "".join(secrets.choice(characters) for _ in range(length))

        for user_id in self.user_ids:
            await self.reset_password(user_id, randomword(32))

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if self.failed_user_ids:
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

        return not self.failed_user_ids

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to reset password of the following users with MAS:",
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
