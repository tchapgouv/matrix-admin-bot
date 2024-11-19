import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import aiofiles
import structlog
from aiohttp import ClientConnectionError
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.util import get_server_name
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand

logger = structlog.getLogger(__name__)


class AccountValidityCommand(SimpleValidatedCommand):
    KEYWORD = "account_validity"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        secure_validator: IValidator = extra_config.get("secure_validator")  # pyright: ignore[reportAssignmentType]

        super().__init__(room, message, matrix_client, secure_validator, extra_config)

        self.get_matrix_ids_fct: Callable[[list[str]], Awaitable[list[str]]] | None = (
            extra_config.get("get_matrix_ids_fct")
        )  # pyright: ignore[reportAttributeAccessIssue]

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.user_ids = event_parser.command(self.KEYWORD).split()

        self.json_report: dict[str, Any] = {"command": self.KEYWORD}
        self.json_report.setdefault("summary", {})
        self.json_report["summary"].setdefault("success", 0)
        self.json_report["summary"].setdefault("failed", 0)
        self.json_report.setdefault("details", {})
        self.json_report.setdefault("failed_users", "")

        self.server_name = get_server_name(self.matrix_client.user_id)

    def is_local_user(self, user_id: str) -> bool:
        return user_id.startswith("@") and get_server_name(user_id) == self.server_name

    @override
    async def should_execute(self) -> bool:
        if self.get_matrix_ids_fct:
            self.user_ids = await self.get_matrix_ids_fct(self.user_ids)
        return any(self.is_local_user(user_id) for user_id in self.user_ids)

    async def account_validity(self, user_id: str, expiration_ts: int) -> bool:
        # TODO check coordinator config
        if get_server_name(user_id) != self.server_name:
            return True

        resp = None
        for retry_nb in range(10):
            try:
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
                    break
                # Let's also stop there if we get a client error that
                # is not a rate limit.
                if resp.status < 500 and resp.status != 429:
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
                "No response from /_synapse/admin/v1/account_validity/validity"
            )
            logger.info("Account Validity failed for %s: %s", user_id, error_message)
            self.json_report["summary"]["failed"] = (
                self.json_report["summary"]["failed"] + 1
            )
            self.json_report["failed_users"] = (
                self.json_report["failed_users"] + user_id + " "
            )
        return True

    @override
    async def simple_execute(self) -> bool:
        users = self.get_users()
        result = len(users) > 0
        if result:
            now_plus_6months_datetime = datetime.now() + timedelta(days=180)  # noqa: DTZ005
            now_plus_6months = int(round(now_plus_6months_datetime.timestamp() * 1000))
            for user_id in users:
                result = result and await self.account_validity(
                    user_id, now_plus_6months
                )
        else:
            self.json_report["summary"]["status"] = "FAILED"
            self.json_report["summary"]["reason"] = "There is no notice to send"

        if self.json_report and result:
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

    async def send_report(self) -> None:
        logger.info("result=%s", self.json_report)
        async with aiofiles.tempfile.NamedTemporaryFile(suffix=".json") as tmpfile:
            await tmpfile.write(
                json.dumps(self.json_report, indent=2, sort_keys=True).encode()
            )
            await tmpfile.flush()
            await self.matrix_client.send_file_message(
                self.room.room_id,
                str(tmpfile.name),
                mime_type="application/json",
                filename=f"{time.strftime('%Y_%m_%d-%H_%M')}-{self.KEYWORD}.json",
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

    def get_users(self) -> set[str]:
        users: set[str] = set()
        for user_id in self.user_ids:
            if self.is_local_user(user_id):
                users.add(user_id)
        return users
