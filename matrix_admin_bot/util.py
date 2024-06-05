from typing import Optional

from nio import RoomMessageText


def get_fallback_stripped_body(reply: RoomMessageText) -> str:
    stripped_body_lines: list[str] = []
    fallback_found = False
    new_line_skipped = False
    for line in reply.body.splitlines():
        if line.startswith("> "):
            fallback_found = True
        elif fallback_found and not new_line_skipped:
            if line.strip() == "":
                new_line_skipped = True
                continue
            else:
                # ...
                stripped_body_lines.append(line)
        else:
            stripped_body_lines.append(line)

    return "\n".join(stripped_body_lines)


def get_server_name(user_or_room_id: str) -> Optional[str]:
    parts = user_or_room_id.split(":")
    if len(parts) < 2:
        return None
    return parts[1]
