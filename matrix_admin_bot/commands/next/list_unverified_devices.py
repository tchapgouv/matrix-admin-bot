from collections.abc import Mapping
from typing import Any, override

import canonicaljson
import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from vodozemac import Ed25519PublicKey, Ed25519Signature, SignatureException

from matrix_admin_bot import UserRelatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class ListUnverifiedDevicesCommand(UserRelatedCommand):
    KEYWORD = "list_unverified_devices"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]

    # TODO decrease complexity
    async def list_unverified_devices(self, user_id: str) -> bool:  # noqa: C901, PLR0911, PLR0912, PLR0915
        if get_server_name(user_id) != self.server_name:
            return True

        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        resp = await self.admin_client.send_to_synapse(
            "POST", "/_matrix/client/v3/keys/query", json={"device_keys": {user_id: []}}
        )
        if not resp.ok:
            self.json_report[user_id]["errors"].append("Can't query device keys")
            return False
        keys = await resp.json()

        all_device_keys = keys.get("device_keys", {}).get(user_id, {})
        if len(all_device_keys) == 0:
            # No device keys so nothing to report
            del self.json_report[user_id]
            return True

        self_signing_keys_and_sigs = keys.get("self_signing_keys", {}).get(user_id, {})
        ed25519_ssk_str = None
        for k, v in self_signing_keys_and_sigs.get("keys", {}).items():
            if k.startswith("ed25519:"):
                ed25519_ssk_str = v
                continue

        if not ed25519_ssk_str:
            self.json_report[user_id]["errors"].append("No SSK available")
            return False

        try:
            ed25519_ssk = Ed25519PublicKey.from_base64(ed25519_ssk_str)
        except:  # noqa: E722
            self.json_report[user_id]["errors"].append("can't parse SSK")
            return False

        # TODO check that SSK is properly signed by the MSK (if not what do we do ??)

        unverified_devices: list[str] = []
        for device_id in all_device_keys:
            if device_id not in all_device_keys:
                unverified_devices.append(device_id)
                self.json_report[user_id].setdefault(
                    "devices_without_device_keys", []
                ).append(device_id)
                continue

            device_keys = all_device_keys[device_id]
            ed25519_key = device_keys.get("keys", {}).get(f"ed25519:{device_id}", None)
            if not ed25519_key:
                unverified_devices.append(device_id)
                self.json_report[user_id].setdefault(
                    "devices_without_ed25519_key", []
                ).append(device_id)
                continue

            key_sig_str = (
                device_keys.get("signatures", {})
                .get(user_id, {})
                .get(f"ed25519:{ed25519_ssk_str}", None)
            )
            if not key_sig_str:
                unverified_devices.append(device_id)
                self.json_report[user_id].setdefault(
                    "devices_without_ssk_signature", []
                ).append(device_id)
                continue

            del device_keys["signatures"]
            del device_keys["unsigned"]
            try:
                ed25519_ssk.verify_signature(
                    canonicaljson.encode_canonical_json(device_keys),
                    Ed25519Signature.from_base64(key_sig_str),
                )
                self.json_report[user_id].setdefault("verified_devices", []).append(
                    device_id
                )
            except SignatureException:
                unverified_devices.append(device_id)
                self.json_report[user_id].setdefault(
                    "devices_with_invalid_ssk_signature", []
                ).append(device_id)

        if len(unverified_devices) == 0:
            del self.json_report[user_id]
            return True

        # TODO handle the case where the identity may have been reset by the attacker
        # In this case we would probably have a recent device verified, and everything
        # else unverified.

        for device_id in unverified_devices:
            resp = await self.admin_client.send_to_synapse(
                "GET", f"/_synapse/admin/v2/users/{user_id}/devices/{device_id}"
            )
            if not resp.ok:
                self.json_report[user_id]["errors"].append(
                    f"Cannot retrieve device details for unverified device {device_id}"
                )
            else:
                self.json_report[user_id].setdefault(
                    "unverified_devices_details", []
                ).append(await resp.json())

        return False

    @override
    async def simple_execute(self) -> bool:
        unverified_users: list[str] = []
        for user_id in self.user_ids:
            res = await self.list_unverified_devices(user_id)
            if not res:
                unverified_users.append(user_id)

        if self.json_report:
            self.json_report["command"] = self.KEYWORD
            await self.send_report()

        if unverified_users:
            text = "\n".join(
                [
                    "The following users has at least one unverified device:",
                    "",
                    *[f"- {user_id}" for user_id in unverified_users],
                ]
            )
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        return True

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!list_unverified_devices <user1> [user2] ...`

**Purpose**:
Lists unverified devices of the specified users.

**Examples**:
- `!list_unverified_devices @user:example.com`
- `!list_unverified_devices @user1:example.com @user2:example.com`
"""
