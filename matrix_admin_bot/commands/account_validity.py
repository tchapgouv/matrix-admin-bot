import asyncio
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import structlog
from aiohttp import ClientConnectionError
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_admin_bot import UserRelatedCommand
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class AccountValidityCommand(UserRelatedCommand):
    KEYWORD = "account_validity"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        logger.debug(
            "Initializing AccountValidityCommand",
            room_id=room.room_id,
            message_id=message.event_id,
        )
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)

        self.json_report["command"] = self.KEYWORD
        self.json_report.setdefault("summary", {})
        self.json_report["summary"].setdefault("success", 0)
        self.json_report["summary"].setdefault("failed", 0)
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")
        logger.debug("Initialized report structure")

    async def account_validity(self, user_id: str, expiration_ts: int) -> bool:
        logger.debug(
            "Setting account validity", user_id=user_id, expiration_ts=expiration_ts
        )
        if get_server_name(user_id) != self.server_name:
            logger.debug("User is not on local server, skipping", user_id=user_id)
            return True

        resp = None
        for retry_nb in range(10):
            try:
                logger.debug(
                    "Attempting to set account validity",
                    attempt=retry_nb + 1,
                    user_id=user_id,
                )
                resp = await self.matrix_client.send(
                    "POST",
                    "/_synapse/admin/v1/account_validity/validity",
                    headers={
                        "Authorization": f"Bearer {self.matrix_client.access_token}"
                    },
                    data=json.dumps(
                        {
                            "user_id": user_id,
                            "expiration_ts": expiration_ts,
                            "enable_renewal_emails": "true",
                        }
                    ),
                )
                if resp.ok:
                    logger.debug("Account validity request successful", user_id=user_id)
                    break
                # Let's also stop there if we get a client error that
                # is not a rate limit.
                if resp.status < 500 and resp.status != 429:
                    logger.debug(
                        "Received non-retryable error",
                        status=resp.status,
                        user_id=user_id,
                    )
                    break
            except ClientConnectionError as e:
                logger.warning("Bot Admin has lost connection for %s: %s", user_id, e)

            # use some backoff
            await asyncio.sleep(0.5 * retry_nb)

        if resp and resp.ok:
            json_body = await resp.json()
            logger.info("Account Validity Done for %s: %s", user_id, str(json_body))
            self.json_report["summary"]["success"] = (
                self.json_report["summary"]["success"] + 1
            )
            self.json_report["details"][user_id] = "SUCCESS"
            logger.debug("Updated report with success", user_id=user_id)

        elif resp:
            json_body = await resp.json()
            logger.info("Account Validity Done for %s: %s", user_id, str(json_body))
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
            self.json_report["details"][user_id] = "FAILED"
            logger.debug("Updated report with failure", user_id=user_id)
        else:
            error_message = (
                "No response from /_synapse/admin/v1/account_validity/validity"
            )
            logger.info("Account Validity failed for %s: %s", user_id, error_message)
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
            self.json_report["details"][user_id] = "FAILED"
            logger.debug("Updated report with no response failure", user_id=user_id)
        return True

    @override
    async def simple_execute(self) -> bool:
        logger.debug("Executing account validity command", user_ids=self.user_ids)
        result = len(self.user_ids) > 0
        if result:
            now_plus_6months_datetime = datetime.now() + timedelta(days=180)  # noqa: DTZ005
            now_plus_6months = round(now_plus_6months_datetime.timestamp() * 1000)
            logger.debug(
                "Setting expiration to 6 months from now",
                expiration_ts=now_plus_6months,
            )
            for user_id in self.user_ids:
                logger.debug("Processing user", user_id=user_id)
                result = result and await self.account_validity(
                    user_id, now_plus_6months
                )
        else:
            logger.warning("No users specified for account validity")
            self.json_report["summary"]["status"] = "FAILED"
            self.json_report["summary"]["reason"] = "There is no notice to send"

        if self.json_report and result:
            logger.debug("Sending report", report=self.json_report)
            await self.send_report()
        return result

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
