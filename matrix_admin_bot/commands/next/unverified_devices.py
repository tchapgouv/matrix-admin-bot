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

from matrix_admin_bot import UserRelatedCommand
from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class UnverifiedDevicesCommand(UserRelatedCommand):
    KEYWORD = "unverified_devices"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, self.KEYWORD, extra_config)
        self.user_ids: list[str] = []
        self.created_after: datetime.date | None = None

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
        # TODO handle the case where the identity may have been reset by the attacker
        # In this case we would probably have a recent device verified, and everything
        # else unverified.

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

        if unverified_devices:
            logger.debug(
                "Found unverified devices",
                user_id=user_id,
                unverified_devices=unverified_devices,
            )

        return unverified_devices

    async def get_mas_unverified_sessions(
        self, user_id: str, unverified_device_ids: Collection[str]
    ) -> dict[str, list[dict[str, Any]]]:
        # Get the user from the MAS with its localpart
        mas_user_id = await self.admin_client.get_mas_user_id(
            self.json_report, [], user_id
        )
        if mas_user_id is None:
            # TODO check if return False will still send the json report or not
            logger.warning("Could not find MAS user", user_id=user_id)
            return {}

        all_device_sessions = await self.admin_client.get_sessions(
            "oauth2", mas_user_id=mas_user_id, user_id=user_id
        )
        all_device_sessions.extend(
            await self.admin_client.get_sessions(
                "compat", mas_user_id=mas_user_id, user_id=user_id
            )
        )

        unverified_device_sessions: dict[str, list[dict[str, Any]]] = {}
        for session in all_device_sessions:
            if not self.is_created_after(session):
                continue

            device_id = session.get("attributes", {}).get("device_id")
            if device_id and device_id in unverified_device_ids:
                unverified_device_sessions.setdefault(device_id, []).append(session)

        logger.debug(
            "Found unverified device sessions",
            user_id=user_id,
            unverified_device_sessions_count=len(unverified_device_sessions),
        )

        return unverified_device_sessions

    async def list_unverified_devices(self, user_id: str) -> bool:
        if get_server_name(user_id) != self.server_name:
            return True

        logger.debug("Listing unverified devices", user_id=user_id)
        self.json_report.setdefault(user_id, {})
        self.json_report[user_id]["errors"] = []

        emails = self.mxid_to_emails.get(user_id, [])
        if emails:
            self.json_report[user_id]["emails"] = emails

        resp = await self.admin_client.send_to_synapse(
            "GET", f"/_synapse/admin/v2/users/{user_id}/devices"
        )
        if not resp.ok:
            logger.warning(
                "Cannot retrieve synapse device details",
                user_id=user_id,
                status=resp.status,
                reason=resp.reason,
            )
            self.json_report[user_id]["errors"].append(
                "Cannot retrieve synapse device details"
            )

        synapse_devices = (await resp.json()).get("devices", [])
        synapse_devices = {
            device.get("device_id"): device for device in synapse_devices
        }

        if len(synapse_devices) == 0:
            logger.debug("No devices found", user_id=user_id)
            del self.json_report[user_id]
            return True

        try:
            res = await self.get_device_keys(user_id)
        except Exception as e:
            logger.info("Failed to get device keys", user_id=user_id, exc_info=e)
            self.json_report[user_id]["errors"].append(str(e))
            # TODO what do we do here???
            # do we want to still propose to logout all sessions?
            return False

        if res is None:
            # No device keys so nothing to report
            logger.debug("No device keys, nothing to report", user_id=user_id)
            del self.json_report[user_id]
            return True

        all_device_keys, ed25519_ssk = res

        unverified_devices = self.compute_unverified_devices(
            user_id, synapse_devices.keys(), all_device_keys, ed25519_ssk
        )

        if len(unverified_devices) == 0:
            logger.debug("No unverified devices found", user_id=user_id)
            del self.json_report[user_id]
            return True

        unverified_device_sessions = await self.get_mas_unverified_sessions(
            user_id, unverified_devices.keys()
        )

        unverified_devices_details: list[dict[str, Any]] = []
        for device_id, sessions in unverified_device_sessions.items():
            device_details = synapse_devices[device_id]
            device_details["reason"] = unverified_devices[device_id]
            device_details["sessions"] = sessions

            if device_id in all_device_keys:
                device_details["keys"] = all_device_keys[device_id]

            unverified_devices_details.append(device_details)

        self.json_report[user_id]["unverified_devices"] = unverified_devices_details

        logger.debug(
            "Unverified devices listed",
            user_id=user_id,
            unverified_devices_count=len(unverified_devices_details),
        )

        return len(unverified_device_sessions) > 0

    def is_created_after(self, session: dict[str, Any]) -> bool:
        if self.created_after is None:
            return True
        created_at_str = session.get("attributes", {}).get("created_at")
        if not created_at_str:
            return True
        created_at = parse_date(created_at_str)
        if not created_at:
            return True
        return created_at > self.created_after

    @override
    async def simple_execute(self) -> bool:
        logger.debug("Unverified devices - started", user_ids=self.user_ids)

        unverified_users: list[str] = []
        for user_id in self.user_ids:
            res = await self.list_unverified_devices(user_id)
            if not res:
                unverified_users.append(user_id)

        if self.json_report:
            await self.send_report()

        if unverified_users:
            nb_unverified_users = len(unverified_users)
            text = f"{'The following ' if nb_unverified_users < 100 else ''}{nb_unverified_users} users has at least one unverified device.\n"  # noqa: E501

            if nb_unverified_users < 100:
                text += "\n".join([f"- {user_id}" for user_id in unverified_users])

            # text += "\nDo you want to remove these unverified devices?"
            # text += "\n\nIf so please reply with 'yes'."

            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        logger.debug(
            "Unverified devices - completed",
            unverified_users_count=len(unverified_users),
        )

        return True

    @override
    async def should_execute(self) -> bool:
        splitted = self.command_text.split()
        if len(splitted) > 0 and splitted[0].startswith("created_after="):
            self.created_after = parse_date(splitted[0][14:])
            self.command_text = " ".join(splitted[1:])

        return await super().should_execute()

    @property
    @override
    def help_message(self) -> str:
        return """
**Usage**:
`!unverified_devices [created_after=2026-01-01T08:00:00] <user1> [user2] ...`

**Purpose**:
Lists and optionally deletes unverified devices and their sessions
for the specified users.

All devices that have not been verified by the user, including devices
that has no crypto setup or no device associated, will be listed and
optionally deleted.

created_after=<ISO formatted date> (optional): only list unverified devices
created after this date.

**Examples**:
- `!unverified_devices @user:example.com`
- `!unverified_devices created_after=2026-01-01 @user1:example.com @user2:example.com`
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
