import datetime
import json
from collections.abc import Awaitable, Callable, Collection, Mapping
from typing import Any, override

import canonicaljson
import dateutil
import structlog
from matrix_bot.bot import MatrixClient
from nio import MatrixRoom, RoomMessage
from vodozemac import Ed25519PublicKey, Ed25519Signature, SignatureException

from matrix_admin_bot import InteractiveValidatedCommand
from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_server_name, is_local_user

logger = structlog.getLogger(__name__)


class UnverifiedSessionsCommand(InteractiveValidatedCommand):
    KEYWORD = "unverified_sessions"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.user_ids: list[str] = []
        self.from_date: datetime.date | None = None

        self.transform_cmd_input_fct: (
            Callable[[type[ICommand], list[str]], Awaitable[list[str]]] | None
        ) = extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

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
        self.json_report[user_id]["self_signing_keys"] = self_signing_keys

        ed25519_ssk_str = get_key(
            "ed25519",
            self_signing_keys.get("keys", {}),
        )
        if not ed25519_ssk_str:
            raise Exception("no ed25519 SSK available")

        try:
            ed25519_ssk = Ed25519PublicKey.from_base64(ed25519_ssk_str)
        except Exception as e:
            raise Exception("SSK could not be parsed") from e

        master_keys = keys.get("master_keys", {}).get(user_id, {})
        self.json_report[user_id]["master_keys"] = master_keys

        ed25519_msk_str = get_key(
            "ed25519",
            master_keys.get("keys", {}),
        )
        if not ed25519_msk_str:
            raise Exception("no ed25519 MSK available")

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
            raise Exception("no ed25519 MSK signature available on the SSK")

        del self_signing_keys["signatures"]
        if "unsigned" in self_signing_keys:
            del self_signing_keys["unsigned"]

        try:
            ed25519_msk.verify_signature(
                canonicaljson.encode_canonical_json(self_signing_keys),
                Ed25519Signature.from_base64(msk_signature),
            )
        except Exception as e:
            raise Exception("ed25519 MSK signature of the SSK is invalid") from e

        return all_device_keys, ed25519_ssk

    def compute_unverified_devices(
        self,
        user_id: str,
        device_ids_to_check: Collection[str],
        all_device_keys: dict[str, Any],
        ed25519_ssk: Ed25519PublicKey,
    ) -> dict[str, str]:
        ed25519_ssk_str = ed25519_ssk.to_base64()

        unverified_devices: dict[str, str] = {}
        for device_id in device_ids_to_check:
            device_keys = all_device_keys.get(device_id)
            if not device_keys:
                unverified_devices[device_id] = "missing_device_keys"
                continue

            ed25519_key = device_keys.get("keys", {}).get(f"ed25519:{device_id}", None)
            if not ed25519_key:
                unverified_devices[device_id] = "missing_ed25519_key"
                continue

            key_sig_str = (
                device_keys.get("signatures", {})
                .get(user_id, {})
                .get(f"ed25519:{ed25519_ssk_str}", None)
            )
            if not key_sig_str:
                unverified_devices[device_id] = "missing_ed25519_ssk_signature"
                continue

            device_keys = device_keys.copy()
            del device_keys["signatures"]
            if "unsigned" in device_keys:
                del device_keys["unsigned"]
            try:
                ed25519_ssk.verify_signature(
                    canonicaljson.encode_canonical_json(device_keys),
                    Ed25519Signature.from_base64(key_sig_str),
                )
            except SignatureException:
                unverified_devices[device_id] = "invalid_ed25519_ssk_signature"

        return unverified_devices

    async def get_mas_unverified_sessions(
        self, user_id: str, unverified_device_ids: Collection[str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:

        # Get the user from the MAS with its localpart
        mas_user_id = await self.admin_client.get_mas_user_id(
            self.json_report, [], user_id
        )
        if mas_user_id is None:
            # TODO check if return False will still send the json report or not
            return [], []

        unverified_device_sessions: list[dict[str, Any]] = []
        unverifiable_sessions: list[dict[str, Any]] = []
        all_sessions = await self.admin_client.get_all_sessions(
            mas_user_id=mas_user_id, user_id=user_id
        )
        for session in all_sessions:
            if not self.is_after_from(session):
                continue

            device_id = session.get("attributes", {}).get("device_id")
            if device_id:
                if device_id in unverified_device_ids:
                    unverified_device_sessions.append(session)
            else:
                unverifiable_sessions.append(session)

        return unverified_device_sessions, unverifiable_sessions

    async def list_unverified_devices(self, user_id: str) -> bool:
        if get_server_name(user_id) != self.server_name:
            return True

        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        resp = await self.admin_client.send_to_synapse(
            "GET", f"/_synapse/admin/v2/users/{user_id}/devices"
        )
        if not resp.ok:
            self.json_report[user_id]["errors"].append(
                "Cannot retrieve synapse device details"
            )

        synapse_devices = (await resp.json()).get("devices", [])
        synapse_devices = {
            device.get("device_id"): device for device in synapse_devices
        }

        try:
            res = await self.get_device_keys(user_id)
        except Exception as e:  # noqa: BLE001
            self.json_report[user_id]["errors"].append(str(e))
            # TODO what do we do here???
            # do we want to still propose to logout all sessions?
            return False

        if res is None:
            # No device keys so nothing to report
            del self.json_report[user_id]
            return True

        all_device_keys, ed25519_ssk = res

        unverified_devices = self.compute_unverified_devices(
            user_id, synapse_devices.keys(), all_device_keys, ed25519_ssk
        )

        if len(unverified_devices) == 0:
            del self.json_report[user_id]
            return True

        unverified_devices_details = []
        for device_id, synapse_device in synapse_devices.items():
            if device_id in unverified_devices:
                reason = unverified_devices[device_id]
                synapse_device["reason"] = reason

                if device_id in all_device_keys:
                    synapse_device["keys"] = all_device_keys[device_id]
                unverified_devices_details.append(synapse_device)

        self.json_report[user_id]["unverified_devices"] = unverified_devices_details

        # TODO handle the case where the identity may have been reset by the attacker
        # In this case we would probably have a recent device verified, and everything
        # else unverified.
        #

        (
            unverified_device_sessions,
            unverifiable_sessions,
        ) = await self.get_mas_unverified_sessions(user_id, unverified_devices.keys())
        self.json_report[user_id]["unverified_device_sessions"] = (
            unverified_device_sessions
        )
        self.json_report[user_id]["unverifiable_sessions"] = unverifiable_sessions

        return False

    def is_after_from(self, session: dict[str, Any]) -> bool:
        if self.from_date is None:
            return True
        created_at_str = session.get("attributes", {}).get("created_at")
        if not created_at_str:
            return True
        created_at = parse_date(created_at_str)
        if not created_at:
            return True
        return created_at > self.from_date

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
                    "The following users has at least one unverified or unverifiable session:",  # noqa: E501
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
        if len(splitted) > 0 and splitted[0].startswith("from="):
            self.from_date = parse_date(splitted[0][5:])
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
`!unverified_sessions [from=2026-01-01T08:00:00] <user1> [user2] ...`

**Purpose**:
Lists and optionally deletes unverified sessions of the specified users.

All sessions that have not been verified by the user, including sessions
that has no crypto setup or no device associated, will be listed and
optionally deleted.

**Examples**:
- `!unverified_sessions @user:example.com`
- `!unverified_sessions @user1:example.com @user2:example.com`
"""


def get_key(key_type: str, keys: dict[str, Any]) -> str | None:
    for k, v in keys.items():
        if k.startswith(f"{key_type}:"):
            return v
    return None


def parse_date(date_str: str) -> datetime.date:
    date = dateutil.parser.parse(date_str)
    if date.tzinfo is None:
        return date.replace(tzinfo=dateutil.tz.tzlocal())
    return date
