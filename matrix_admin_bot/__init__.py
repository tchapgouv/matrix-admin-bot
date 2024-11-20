import json
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import aiofiles
import structlog
from matrix_bot.client import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from typing_extensions import override

from matrix_command_bot.util import get_server_name, is_local_user
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.simple_command import SimpleValidatedCommand

logger = structlog.getLogger(__name__)


class UserRelatedCommand(SimpleValidatedCommand):
    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        keyword: str,
        extra_config: Mapping[str, Any],
    ) -> None:
        secure_validator: IValidator = extra_config.get("secure_validator")  # pyright: ignore[reportAssignmentType]

        super().__init__(room, message, matrix_client, secure_validator, extra_config)

        self.keyword = keyword

        self.get_matrix_ids_fct: Callable[[list[str]], Awaitable[list[str]]] | None = (
            extra_config.get("get_matrix_ids_fct")
        )  # pyright: ignore[reportAttributeAccessIssue]

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.user_ids = event_parser.command(keyword).split()

        self.server_name = get_server_name(self.matrix_client.user_id)

        self.json_report: dict[str, Any] = {}

    @override
    async def should_execute(self) -> bool:
        if self.get_matrix_ids_fct:
            self.user_ids = await self.get_matrix_ids_fct(self.user_ids)
        return any(
            is_local_user(user_id, self.server_name) for user_id in self.user_ids
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
                filename=f"{time.strftime('%Y_%m_%d-%H_%M')}-{self.keyword}.json",
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )
