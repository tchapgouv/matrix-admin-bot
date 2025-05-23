import json
import time
from typing import Any

import aiofiles
import structlog
from matrix_bot.bot import MatrixClient
from nio import RoomMessageText

from matrix_command_bot.command import ICommand

logger = structlog.getLogger(__name__)


def get_fallback_stripped_body(reply: RoomMessageText) -> str:
    logger.debug(
        "get_fallback_stripped_body called", reply_id=getattr(reply, "event_id", None)
    )
    stripped_body_lines: list[str] = []
    fallback_found = False
    new_line_found = False
    for line in reply.body.splitlines():
        if line.startswith("> "):
            fallback_found = True
        elif fallback_found and not new_line_found:
            if line.strip() == "":
                new_line_found = True
                continue
            # Out of spec...
            stripped_body_lines.append(line)
        else:
            stripped_body_lines.append(line)

    return "\n".join(stripped_body_lines)


def get_server_name(user_or_room_id: str) -> str | None:
    logger.debug("get_server_name called", user_or_room_id=user_or_room_id)
    parts = user_or_room_id.split(":")
    if len(parts) < 2:
        return None
    return parts[1]


def is_local_user(user_id: str, server_name: str | None) -> bool:
    logger.debug("is_local_user called", user_id=user_id, server_name=server_name)
    return user_id.startswith("@") and get_server_name(user_id) == server_name


async def send_report(
    json_report: dict[str, Any],
    report_name: str,
    matrix_client: MatrixClient,
    room_id: str,
    replied_event_id: str,
) -> None:
    logger.debug("send_report called", report_name=report_name, room_id=room_id)
    async with aiofiles.tempfile.NamedTemporaryFile(suffix=".json") as tmpfile:
        await tmpfile.write(json.dumps(json_report, indent=2, sort_keys=True).encode())
        await tmpfile.flush()
        logger.debug("Sending file message", filename=tmpfile.name)
        await matrix_client.send_file_message(
            room_id,
            str(tmpfile.name),
            mime_type="application/json",
            filename=f"{time.strftime('%Y_%m_%d-%H_%M')}-{report_name}.json",
            reply_to=replied_event_id,
            thread_root=replied_event_id,
        )


async def set_status_reaction(
    command: ICommand,
    key: str | None,
    current_reaction_event_id: str | None,
) -> str | None:
    logger.debug(
        "set_status_reaction called",
        command=type(command).__name__,
        key=key,
        current_reaction_event_id=current_reaction_event_id,
    )
    if key is None:
        return None

    if current_reaction_event_id:
        logger.debug("Redacting previous reaction", event_id=current_reaction_event_id)
        await command.matrix_client.room_redact(
            command.room.room_id, current_reaction_event_id
        )

    if key:
        logger.debug("Sending new reaction", key=key)
        return await command.matrix_client.send_reaction(
            command.room.room_id, command.message, key
        )

    return None
