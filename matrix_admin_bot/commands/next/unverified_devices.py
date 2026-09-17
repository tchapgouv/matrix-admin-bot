import datetime
import json
from collections.abc import Awaitable, Callable, Collection, Mapping
from typing import Any, override

import canonicaljson
import dateutil
import structlog
from matrix_bot.bot import MatrixClient
from matrix_bot.eventparser import MessageEventParser
from nio import MatrixRoom, RoomMessage
from vodozemac import Ed25519PublicKey, Ed25519Signature, SignatureException

from matrix_admin_bot.admin_client import AdminClient
from matrix_command_bot.step import (
    CommandAction,
    CommandWithSteps,
    ExecuteFunctionStep,
    ICommandStep,
)
from matrix_command_bot.step.reaction_steps import (
    ReactionCommandState,
    ReactionStep,
    ResultReactionStep,
)
from matrix_command_bot.util import (
    get_server_name,
    is_local_user,
    send_report,
)
from matrix_command_bot.validation import IValidator
from matrix_command_bot.validation.steps import ValidateStep

logger = structlog.getLogger(__name__)


class UnverifiedDevicesState(ReactionCommandState):
    def __init__(self) -> None:
        super().__init__()
        self.unverified_users: list[str] = []
        self.sessions_to_delete: dict[str, list[dict[str, Any]]] = {}


class ValidateDeleteStep(ValidateStep):
    """Ask for a validation code before deleting, unless there is nothing
    to delete."""

    def __init__(self, command: "UnverifiedDevicesCommand") -> None:
        super().__init__(
            command,
            command.state,
            command.validator,
            command.delete_confirm_message,
        )
        self.command: UnverifiedDevicesCommand = command

    @override
    async def execute(
        self, reply: RoomMessage | None = None
    ) -> tuple[bool, CommandAction]:
        if not self.command.state.sessions_to_delete:
            logger.debug(
                "No unverified session to delete, skipping validation",
                command=self.command,
            )
            return True, CommandAction.CONTINUE

        # The confirm message can only be computed once the listing is done.
        self.message = self.command.delete_confirm_message
        return await super().execute(reply)


class UnverifiedDevicesCommand(CommandWithSteps):
    KEYWORD = "unverified_devices"

    def __init__(
        self,
        room: MatrixRoom,
        message: RoomMessage,
        matrix_client: MatrixClient,
        extra_config: Mapping[str, Any],
    ) -> None:
        super().__init__(room, message, matrix_client, extra_config)
        self.admin_client: AdminClient = extra_config.get("admin_client")  # pyright: ignore[reportAttributeAccessIssue]
        self.validator: IValidator = extra_config.get("validator")  # pyright: ignore[reportAttributeAccessIssue]
        self.transform_cmd_input_fct: (
            Callable[[list[str]], Awaitable[list[str]]] | None
        ) = extra_config.get("transform_cmd_input_fct")  # pyright: ignore[reportAttributeAccessIssue]

        self.state = UnverifiedDevicesState()

        event_parser = MessageEventParser(
            room=room, event=message, matrix_client=matrix_client
        )
        event_parser.do_not_accept_own_message()
        self.command_text = event_parser.command(self.KEYWORD).strip()

        server_name = get_server_name(self.matrix_client.user_id)
        assert server_name  # noqa: S101
        self.server_name: str = server_name

        self.user_ids: list[str] = []
        self.mxid_to_emails: dict[str, list[str]] = {}
        self.created_after: datetime.date | None = None

        self.json_report: dict[str, Any] = {}

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

    async def get_devices_sessions(
        self, user_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        # Get the user from the MAS with its localpart
        mas_user_id = await self.admin_client.get_mas_user_id(
            self.json_report, [], user_id
        )
        if mas_user_id is None:
            # TODO check if return False will still send the json report or not
            logger.warning("Could not find MAS user", user_id=user_id)
            return {}

        all_sessions = await self.admin_client.get_sessions(
            "oauth2", mas_user_id=mas_user_id, user_id=user_id
        )
        all_sessions.extend(
            await self.admin_client.get_sessions(
                "compat", mas_user_id=mas_user_id, user_id=user_id
            )
        )

        devices_sessions: dict[str, list[dict[str, Any]]] = {}
        for session in all_sessions:
            device_id = session.get("attributes", {}).get("device_id")
            if device_id:
                devices_sessions.setdefault(device_id, []).append(session)

        return devices_sessions

    # TODO decrease complexity
    async def list_unverified_devices(self, user_id: str) -> bool:  # noqa: C901,PLR0911
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

        devices_sessions = await self.get_devices_sessions(user_id)

        if not self.has_unverified_devices_created_after(
            unverified_devices.keys(), devices_sessions
        ):
            del self.json_report[user_id]
            return True

        self.state.sessions_to_delete[user_id] = [
            session
            for device_id in unverified_devices
            for session in devices_sessions.get(device_id, [])
            if self.is_created_after(session)
        ]

        verified_devices = list(synapse_devices.keys() - unverified_devices.keys())

        self.json_report[user_id]["unverified_devices"] = unverified_devices
        self.json_report[user_id]["verified_devices"] = verified_devices

        devices_details: list[dict[str, Any]] = []
        for device_id, details in synapse_devices.items():
            details["sessions"] = devices_sessions.get(device_id, [])

            if device_id in all_device_keys:
                details["keys"] = all_device_keys[device_id]

            devices_details.append(details)

        self.json_report[user_id]["devices_details"] = devices_details
        last_seen_verified_device_ts = max(
            (
                details.get("last_seen_ts", 0) / 1000
                for device_id, details in synapse_devices.items()
                if device_id in verified_devices
            ),
            default=None,
        )

        if last_seen_verified_device_ts:
            self.json_report[user_id]["last_seen_verified_device"] = (
                datetime.datetime.fromtimestamp(
                    last_seen_verified_device_ts, tz=datetime.UTC
                ).isoformat()
            )

        logger.debug(
            "Unverified devices listed",
            user_id=user_id,
            unverified_devices_count=len(unverified_devices),
        )

        return False

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

    def has_unverified_devices_created_after(
        self, unverified_device_ids: Collection[str], device_sessions: dict[str, Any]
    ) -> bool:
        for device_id in unverified_device_ids:
            sessions = device_sessions.get(device_id, [])
            for session in sessions:
                if self.is_created_after(session):
                    return True
        return False

    async def list_all_unverified_devices(self) -> bool:
        logger.debug("Unverified devices - started", user_ids=self.user_ids)

        for user_id in self.user_ids:
            res = await self.list_unverified_devices(user_id)
            if not res:
                self.state.unverified_users.append(user_id)

        if self.json_report:
            await self.send_report()

        unverified_users_count = len(self.state.unverified_users)

        logger.debug(
            "Unverified devices - listed",
            unverified_users_count=unverified_users_count,
            sessions_to_delete_count=sum(
                len(sessions) for sessions in self.state.sessions_to_delete.values()
            ),
        )

        if self.state.unverified_users:
            if unverified_users_count < 100:
                text = f"The following {unverified_users_count} users "
            else:
                text = f"{unverified_users_count} users "
            text += "has at least one matching unverified device.\n"

            if unverified_users_count < 100:
                text += "\n".join(
                    [f"- {user_id}" for user_id in self.state.unverified_users]
                )

            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        return True

    async def delete_unverified_sessions(self) -> bool:
        failed_sessions: list[str] = []
        for user_id, sessions in self.state.sessions_to_delete.items():
            for session in sessions:
                if await self.admin_client.delete_session(session):
                    logger.debug(
                        "Unverified session deleted",
                        user_id=user_id,
                        session_id=session.get("id"),
                    )
                else:
                    failed_sessions.append(session.get("id", "unknown"))
                    logger.warning(
                        "Cannot delete unverified session",
                        user_id=user_id,
                        session_id=session.get("id"),
                    )

        if failed_sessions:
            text = "\n".join(
                [
                    "Couldn't delete the following sessions:",
                    "",
                    *[f"- {session_id}" for session_id in failed_sessions],
                ]
            )
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                text,
                reply_to=self.message.event_id,
                thread_root=self.message.event_id,
            )

        return not failed_sessions

    async def should_execute(self) -> bool:
        splitted = self.command_text.split()
        if len(splitted) > 0 and splitted[0].startswith("created_after="):
            self.created_after = parse_date(splitted[0][14:])
            self.command_text = " ".join(splitted[1:])

        (
            self.user_ids,
            self.mxid_to_emails,
        ) = await self.admin_client.get_mxids_from_args(
            self.command_text.split(), self.server_name, self.transform_cmd_input_fct
        )
        return any(
            is_local_user(user_id, self.server_name) for user_id in self.user_ids
        )

    @override
    async def create_steps(self) -> list[ICommandStep]:
        return [
            ExecuteFunctionStep(self, self.should_execute, abort_on_failure=True),
            # Validate the command before listing and reporting the devices.
            ValidateStep(self, self.state, self.validator),
            ReactionStep(self, self.state, "🚀"),
            ExecuteFunctionStep(self, self.list_all_unverified_devices),
            # Validate again before deleting the reported sessions.
            ValidateDeleteStep(self),
            ExecuteFunctionStep(self, self.delete_unverified_sessions),
            ResultReactionStep(self, self.state),
        ]

    @override
    async def execute(self) -> bool:
        if self.command_text == "help":
            await self.send_help()
            return True

        return await super().execute()

    async def send_help(self) -> None:
        if self.extra_config.get("is_coordinator", True):
            await self.matrix_client.send_markdown_message(
                self.room.room_id,
                self.help_message,
            )

    async def send_report(self) -> None:
        await send_report(
            json_report=self.json_report,
            report_name=self.KEYWORD,
            matrix_client=self.matrix_client,
            room_id=self.room.room_id,
            replied_event_id=self.message.event_id,
        )

    @property
    def delete_confirm_message(self) -> str | None:
        lines = [
            "Do you want to delete the reported unverified devices?",
            "",
        ]
        return "\n".join(lines)

    @property
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

**Steps**:
1. The command first asks for a validation code
2. The command lists the unverified devices and sends a report
3. If some unverified sessions have been reported, it asks for a
validation code again
4. Once validated, the reported unverified sessions are deleted

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
