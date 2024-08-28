import json
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import aiofiles
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.util import get_server_name
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand


class AccountValidityCommand(SimpleValidatedCommand):
    KEYWORD = "account_validity"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        secure_validator: IValidator = extra_config.get("secure_validator")  # type: ignore[reportAssignmentType]

        super().__init__(room, message, matrix_client, secure_validator, extra_config)

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.user_ids = event_parser.command(self.KEYWORD).split()

        self.failed_user_ids: list[str] = []

        self.json_report: dict[str, Any] = {}

        self.server_name = get_server_name(self.matrix_client.user_id)

    async def account_validity(self, user_id: str, expiration_ts: int) -> bool:
        # TODO check coordinator config
        if get_server_name(user_id) != self.server_name:
            return True

        self.json_report.setdefault(user_id, {})

        resp = await self.matrix_client.send(
            "POST",
            "/_synapse/admin/v1/account_validity/validity",
            headers={"Authorization": f"Bearer {self.matrix_client.access_token}"},
            data=json.dumps(
                {
                    "user_id": user_id,
                    "expiration_ts": expiration_ts,
                    "enable_renewal_emails": "true",
                }
            ),
        )
        if not resp.ok:
            json_body = await resp.json()
            self.json_report[user_id].update(json_body)
            self.failed_user_ids.append(user_id)
            return False

        return True

    @override
    async def simple_execute(self) -> bool:
        now_plus_6months_datetime = datetime.now() + timedelta(days=180)  # noqa: DTZ005
        now_plus_6months = int(round(now_plus_6months_datetime.timestamp() * 1000))
        for user_id in self.user_ids:
            await self.account_validity(user_id, now_plus_6months)

        if self.failed_user_ids:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        return not self.failed_user_ids

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

        if self.failed_user_ids:
            text = "\n".join(
                [
                    "Couldn't set the account validity of the following users:",
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
