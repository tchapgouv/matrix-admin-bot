import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, override

import canonicaljson
import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from vodozemac import Ed25519PublicKey, Ed25519Signature, SignatureException

from matrix_admin_bot import InteractiveValidatedCommand
from matrix_admin_bot.commands.next.admin_client import AdminClient
from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_server_name, is_local_user

logger = structlog.getLogger(__name__)


class ListUnverifiedDevicesCommand(InteractiveValidatedCommand):
    KEYWORD = "list_unverified_devices"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)

        self.transform_cmd_input_fct: (
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
        ) = extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]

    async def get_device_keys(
        self, user_id: str
    ) -> tuple[dict[str, Any], Ed25519PublicKey] | None:
        """Get the device keys for a user. Parsed SSK will also be returned,
        after verifying that it has been properly signed by the MSK."""

        resp = await self.admin_client.send_to_synapse(
            "POST",
            "/_matrix/client/v3/keys/query",
            data=json.dumps({"device_keys": {user_id: []}}),
        )
        if not resp.ok:
            raise Exception("Can't query device keys")
        keys = await resp.json()

        all_device_keys = keys.get("device_keys", {}).get(user_id, {})
        if len(all_device_keys) == 0:
            return None

        self_signing_keys = keys.get("self_signing_keys", {}).get(user_id, {})
        ed25519_ssk_str = get_key(
            "ed25519",
            self_signing_keys.get("keys", {}),
        )

        if not ed25519_ssk_str:
            raise Exception("no SSK available")

        try:
            ed25519_ssk = Ed25519PublicKey.from_base64(ed25519_ssk_str)
        except Exception as e:
            raise Exception("SSK could not be parsed") from e

        ed25519_msk_str = get_key(
            "ed25519",
            keys.get("master_keys", {}).get(user_id, {}).get("keys", {}),
        )

        if not ed25519_msk_str:
            raise Exception("no MSK available")

        try:
            ed25519_msk = Ed25519PublicKey.from_base64(ed25519_msk_str)
        except Exception as e:
            raise Exception("MSK could not be parsed") from e

        msk_signature = (
            self_signing_keys.get("signatures", {})
            .get(user_id, {})
            .get(f"ed25519:{ed25519_msk_str}")
        )
        if not msk_signature:
            raise Exception("no MSK signature available on the SSK")

        del self_signing_keys["signatures"]
        if "unsigned" in self_signing_keys:
            del self_signing_keys["unsigned"]

        try:
            ed25519_msk.verify_signature(
                canonicaljson.encode_canonical_json(self_signing_keys),
                Ed25519Signature.from_base64(msk_signature),
            )
        except Exception as e:
            raise Exception("MSK signature of the SSK is invalid") from e

        return all_device_keys, ed25519_ssk

    # TODO decrease complexity
    async def list_unverified_devices(self, user_id: str) -> bool:  # noqa: C901
        if get_server_name(user_id) != self.server_name:
            return True

        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        try:
            res = await self.get_device_keys(user_id)
        except Exception as e:  # noqa: BLE001
            self.json_report[user_id]["errors"].append(str(e))
            return False

        if res is None:
            # No device keys so nothing to report
            del self.json_report[user_id]
            return True

        all_device_keys, ed25519_ssk = res
        ed25519_ssk_str = ed25519_ssk.to_base64()

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
            if "unsigned" in device_keys:
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

        mas_user_id = await self.admin_client.get_mas_user_id(
            self.json_report, [], user_id
        )
        if mas_user_id is None:
            return False

        mas_devices_sessions = await self.admin_client.get_oauth2_sessions(
            self.json_report, [], mas_user_id, user_id
        )
        mas_devices_sessions.update(
            await self.admin_client.get_compat_sessions(
                self.json_report, [], mas_user_id, user_id
            )
        )
        self.json_report[user_id]["mas_devices_sessions"] = mas_devices_sessions

        synapse_devices = {}
        resp = await self.admin_client.send_to_synapse(
            "GET", f"/_synapse/admin/v2/users/{user_id}/devices"
        )

        if not resp.ok:
            self.json_report[user_id]["errors"].append("Cannot retrieve device details")

        synapse_devices = (await resp.json()).get("devices", [])
        self.json_report[user_id]["synapse_devices"] = synapse_devices

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

    @override
    async def should_execute(self) -> bool:
        splitted = self.command_text.split()
        self.from_ts = None
        if len(splitted) > 0 and splitted[0].startswith("from_ts="):
            self.from_ts = int(splitted[0][8:])
            splitted = splitted[1:]

        self.user_ids = splitted

        if self.transform_cmd_input_fct:
            self.user_ids = await self.transform_cmd_input_fct(
                self.__class__, self.user_ids
            )
        return any(
            is_local_user(user_id, self.server_name) for user_id in self.user_ids
        )

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!list_unverified_devices [from_ts=1782307502] <user1> [user2] ...`

**Purpose**:
Lists unverified devices of the specified users.

**Examples**:
- `!list_unverified_devices @user:example.com`
- `!list_unverified_devices @user1:example.com @user2:example.com`
"""


def get_key(key_type: str, keys: dict[str, Any]) -> str | None:
    for k, v in keys.items():
        if k.startswith(f"{key_type}:"):
            return v
    return None
