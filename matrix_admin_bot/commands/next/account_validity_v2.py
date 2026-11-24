import asyncio
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, override

import structlog

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.admin_client import AdminClient
from matrix_command_bot.util import get_server_name

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aiohttp import ClientResponse
    from matrix_bot.bot import MatrixClient
    from nio import MatrixRoom, RoomMessage


logger = structlog.getLogger(__name__)


class AccountValidityCommandV2(UserRelatedCommand):
    KEYWORD = "account_validity"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.limit: int = extra_config.get("server_notice_limit", 100)  # pyright: ignore[reportAttributeAccessIssue]
        self.nb_workers: int = extra_config.get("server_notice_nb_workers", 1)  # pyright: ignore[reportAttributeAccessIssue]

        self.json_report["command"] = self.KEYWORD
        self.json_report.setdefault("summary", {})
        self.json_report["summary"].setdefault("success", 0)
        self.json_report["summary"].setdefault("failed", 0)
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")

    async def _send_with_retry(
        self, user_id: str, expiration_ts: int
    ) -> ClientResponse | None:
        resp = None
        for retry_nb in range(3):
            try:
                resp = await self.admin_client.send_to_synapse(
                    "POST",
                    "/_synapse/client/email_account_validity/admin",
                    data=json.dumps(
                        {
                            "user_id": user_id,
                            "expiration_ts": expiration_ts,
                            "enable_renewal_emails": "true",
                        }
                    ),
                )
                if await self._stop_retry(resp):
                    break
            except Exception as e:
                logger.warning(
                    "Bot Admin has lost connection for %s", user_id, exc_info=e
                )
            await asyncio.sleep(0.5 * retry_nb)
        return resp

    async def _stop_retry(self, resp: ClientResponse) -> bool:
        if resp.ok or (resp.status < 500 and resp.status != 429):
            return True
        # NOTE: Synapse replied a 'User not found' with an error 500 - "M_FORBIDDEN"
        if resp.status == 500:
            json_body = await resp.json()
            return json_body.get("errcode") == "M_FORBIDDEN"
        return False

    async def _handle_response(self, user_id: str, resp: ClientResponse | None) -> bool:
        if resp and resp.ok:
            json_body = await resp.json()
            logger.info("Account Validity Done for %s: %s", user_id, str(json_body))
            self.json_report["summary"]["success"] = (
                self.json_report["summary"]["success"] + 1
            )
        elif resp:
            json_body = await resp.json()
            logger.info("Account Validity Done for %s: %s", user_id, str(json_body))
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
        else:
            error_message = (
                "No response from /_synapse/client/email_account_validity/admin"
            )
            logger.info("Account Validity failed for %s: %s", user_id, error_message)
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
        return True

    async def account_validity(self, user_id: str, expiration_ts: int) -> bool:
        if get_server_name(user_id) != self.server_name:
            return True

        resp = await self._send_with_retry(user_id, expiration_ts)
        return await self._handle_response(user_id, resp)

    @override
    async def simple_execute(self) -> bool:
        is_valid = len(self.user_ids) > 0
        if is_valid:
            now_plus_6months_datetime = datetime.now() + timedelta(days=180)  # noqa: DTZ005
            now_plus_6months = round(now_plus_6months_datetime.timestamp() * 1000)
            for user_id in self.user_ids:
                is_valid = is_valid and await self.account_validity(
                    user_id, now_plus_6months
                )
        else:
            self.json_report["summary"]["status"] = "FAILED"
            self.json_report["summary"]["reason"] = "There is no notice to send"

        if self.json_report and is_valid:
            await self.send_report()
        return is_valid

    @property
    @override
    def confirm_message(self) -> str | None:
        return "\n".join(
            [
                "You are about to set the account validity of the following users:",
                "",
                *[f"- {user_id}" for user_id in self.user_ids],
            ]
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!account_validity <user1> [user2] ...`

**Purpose**:
Extends the validity period of user accounts.

**Effects**:
- Sets the account expiration timestamp to 180 days (6 months) from now

**Examples**:
- `!account_validity @user:example.com`
- `!account_validity @user1:example.com user2@example.com`
"""
