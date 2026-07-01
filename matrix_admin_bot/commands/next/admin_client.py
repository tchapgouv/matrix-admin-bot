import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
import structlog
from aiohttp import ClientResponse
from matrix_bot.client import MatrixClient
from requests import Response

from matrix_command_bot.util import get_localpart_from_id

logger = structlog.getLogger(__name__)

VERIFY_SSL_CERT = True


class AdminClient:
    """
    Admin Client
    """

    def __init__(
        self,
        synapse_client: MatrixClient,
        mas_base_url: str,
        mas_access_token: str,
    ) -> None:
        self.base_url = mas_base_url.rstrip("/")
        self.access_token = mas_access_token

        self.synapse_client = synapse_client
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "matrix-admin-bot",
                "Authorization": f"Bearer {self.access_token}",
            }
        )
        self.session.verify = VERIFY_SSL_CERT

    def send_to_mas(self, method: str, endpoint: str, **kwargs: Any) -> Response:  # noqa: ANN401
        url = f"{self.base_url}" + endpoint
        return self.session.request(method, url, **kwargs)

    async def send_to_synapse(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> ClientResponse:
        if headers is None:
            headers = {}
        headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "matrix-admin-bot",
                "Authorization": f"Bearer {self.access_token}",
            }
        )
        return await self.synapse_client.send(
            method, endpoint, headers=headers, **kwargs
        )

    async def is_email_valid(
        self, server_name: str | None, email: str | None
    ) -> tuple[bool, str]:
        if email is None or email.startswith("@") or "@" not in email:
            return False, f"Email={email} is not valid: missing @"
        homeserver = await self.get_homeserver(email)
        result: bool = homeserver is not None and homeserver == server_name
        if not result:
            return False, f"Email={email} is not valid: Wrong homeserver-{homeserver}"
        return True, ""

    async def get_homeserver(self, email: str) -> str | None:
        resp = await self.send_to_synapse(
            "GET", f"/_matrix/identity/api/v1/info?medium=email&address={email}"
        )
        if resp.ok:
            json_body = await self.decode_client_response(resp)
            return json_body.get("hs", None)
        return None

    async def get_mas_user_id(
        self, json_report: dict[str, Any], failed_user_ids: list[str], user_id: str
    ) -> str | None:
        username = get_localpart_from_id(user_id)
        endpoint = f"/api/admin/v1/users/by-username/{username}"
        resp = self.send_to_mas("GET", endpoint=endpoint)

        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot get user from localpart {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return None
        return json_body["data"]["id"]

    async def get_users(
        self, server_name: str | None, json_report: dict[str, Any], limit: int = 100
    ) -> set[str]:
        if server_name is None:
            return set()

        users: set[str] = set()
        endpoint = f"/api/admin/v1/users?filter[status]=active&page[first]={limit}"
        resp = await self.send_to_mas_with_retry(endpoint)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = "Cannot get all users from MAS"
            json_report["details"]["get_users"] = {
                "error": error,
                "description": json_body,
            }
            logger.warning(
                "%s - %s users has been retrieved: %s",
                error,
                len(users),
                f"{resp.status_code}-{resp.reason}-{json_body}",
            )
            return users

        nb_users = 0
        if json_body.get("meta") and json_body.get("meta").get("count"):
            nb_users = json_body["meta"]["count"]

        while True:
            users = users | {
                f"@{user['attributes']['username']}:{server_name}"
                for user in json_body["data"]
                if user["type"] == "user"
            }
            # Update user count
            if json_body.get("meta") and json_body.get("meta").get("count"):
                nb_users = json_body["meta"]["count"]
            if json_body.get("links") and json_body.get("links").get("next"):
                endpoint = json_body["links"]["next"]
                resp = await self.send_to_mas_with_retry(endpoint)
                json_body = await self.decode_response(resp)
                if not resp.ok:
                    error = "Cannot get all users from MAS"
                    json_report["details"]["get_users"] = {
                        "error": error,
                        "description": json_body,
                    }
                    logger.warning(
                        "%s - %s users has been retrieved: %s",
                        error,
                        len(users),
                        f"{resp.status_code}-{resp.reason}-{json_body}",
                    )
                    return set()
            else:
                break

        # Check if we have retrieve all users
        if nb_users > len(users):
            logger.warning(
                "Not all users have been retrieved : %s/%s users", len(users), nb_users
            )
            error = "Cannot get all users from MAS"
            json_report["details"]["get_users"] = {
                "error": error,
                "description": f"Not all users have been retrieved : "
                f"{len(users)}/{nb_users} users",
            }
            return set()

        return users

    async def send_to_mas_with_retry(
        self, endpoint: str, max_retry: int = 5
    ) -> Response:
        for retry_nb in range(max_retry):
            try:
                resp = self.send_to_mas("GET", endpoint=endpoint)
                if resp.ok:
                    return resp
            except Exception as e:  # noqa: BLE001
                logger.warning("Request to MAS has failed", exc_info=e)
                # use some backoff
                await asyncio.sleep(0.5 * retry_nb)

        resp = Response()
        resp.status_code = 500
        resp.reason = "Internal Server Error"
        return resp

    async def decode_response(self, resp: Response) -> Any:  # noqa: ANN401
        if resp.headers.get("Content-Type", "").startswith("application/json") is True:
            return resp.json()
        return resp.text

    async def decode_client_response(self, resp: ClientResponse) -> Any:  # noqa: ANN401
        if resp.headers.get("Content-Type", "").startswith("application/json") is True:
            return await resp.json()
        return await resp.text()

    async def get_devices_from_synapse(
        self, json_report: dict[str, Any], user_id: str
    ) -> None:
        endpoint = f"/_synapse/admin/v2/users/{user_id}/devices"
        resp = await self.send_to_synapse(
            "GET",
            endpoint=endpoint,
        )
        if resp.ok:
            json_body = await resp.json()
            json_report[user_id]["devices"] = json_body.get("devices", [])
            logger.info("Devices : %s", json_report[user_id]["devices"])

    async def get_user_from_synapse(
        self, json_report: dict[str, Any], failed_user_ids: list[str], user_id: str
    ) -> bool:
        endpoint = f"/_synapse/admin/v2/users/{user_id}"
        resp = await self.send_to_synapse(
            "GET",
            endpoint=endpoint,
        )
        if resp.ok:
            json_body = await resp.json()
            json_report[user_id]["user"] = json_body
            json_report[user_id]["user"]["creation_ts_formatted"] = format_timestamp(
                json_report[user_id]["user"]["creation_ts"]
            )
            json_report[user_id]["user"]["last_seen_ts_formatted"] = format_timestamp(
                json_report[user_id]["user"]["last_seen_ts"]
            )
            return True
        json_body = await resp.json()
        error = f"Cannot get user information from localpart {user_id}"
        json_report[user_id]["errors"].append(
            {"error": error, "description": json_body}
        )
        failed_user_ids.append(user_id)
        return False

    async def get_compat_sessions(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> None:
        params = {"filter[user]": mas_user_id, "filter[status]": "active"}
        endpoint = "/api/admin/v1/compat-sessions"
        resp = self.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = await self.decode_response(resp)
        if resp.ok:
            count = json_body["meta"]["count"]
            if count > 0:
                sessions = json_body["data"]
                json_report[user_id]["sessions"]["compat-sessions"] = sessions
                logger.debug(
                    "Compat-Sessions : %s",
                    json_report[user_id]["sessions"]["compat-sessions"],
                )
        else:
            error = f"Cannot get compat session  from localpart {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)

    async def get_user_sessions(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> None:
        params = {"filter[user]": mas_user_id, "filter[status]": "active"}
        endpoint = "/api/admin/v1/user-sessions"
        resp = self.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = await self.decode_response(resp)
        if resp.ok:
            count = json_body["meta"]["count"]
            if count > 0:
                sessions = json_body["data"]
                json_report[user_id]["sessions"]["user-sessions"] = sessions
                logger.debug(
                    "User-Sessions : %s",
                    json_report[user_id]["sessions"]["user-sessions"],
                )
        else:
            error = f"Cannot get user session for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)

    async def get_oauth2_sessions(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> None:
        params = {"filter[user]": mas_user_id, "filter[status]": "active"}
        endpoint = "/api/admin/v1/oauth2-sessions"
        resp = self.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = await self.decode_response(resp)
        if resp.ok:
            count = json_body["meta"]["count"]
            if count > 0:
                sessions = json_body["data"]
                json_report[user_id]["sessions"]["oauth2-sessions"] = sessions
                logger.debug(
                    "OAuth2-Sessions : %s",
                    json_report[user_id]["sessions"]["oauth2-sessions"],
                )
        else:
            error = f"Cannot get oauth2 session for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)

    async def set_password(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        password: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/set-password"
        data = {"password": password, "skip_password_check": True}
        resp = self.send_to_mas("POST", endpoint=endpoint, json=data)
        if not resp.ok:
            json_body = await self.decode_response(resp)
            error = f"Cannot reset password for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        return True

    async def kill_all_sessions(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/kill-sessions"
        resp = self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot kill all sessions {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        return True

    async def lock(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/lock"
        resp = self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot lock for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        json_report[user_id]["description"] = json_body["data"]
        return True

    async def unlock(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/unlock"
        resp = self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot unlock for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        json_report[user_id]["description"] = json_body["data"]
        return True

    async def deactivate(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/deactivate"
        data = {"skip_erase": True}
        resp = self.send_to_mas("POST", endpoint=endpoint, json=data)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot deactivate for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        json_report[user_id]["description"] = json_body["data"]
        return True

    async def reactivate(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/users/{mas_user_id}/reactivate"
        resp = self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot reactivate for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        json_report[user_id]["description"] = json_body["data"]
        return True

    async def find_emails(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        user_id: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        endpoint = "/api/admin/v1/user-emails"
        resp = self.send_to_mas("GET", endpoint=endpoint, params=params)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            if resp.status_code == 404:
                return []
            error = f"Cannot find emails with {params} for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return None
        json_report[user_id]["description"] = json_body["data"]
        return json_body["data"]

    async def remove_email(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        user_email_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/user-emails/{user_email_id}"
        resp = self.send_to_mas("DELETE", endpoint=endpoint)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot remove email {user_email_id} for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        return True

    async def add_email(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
        email: str,
    ) -> bool:
        endpoint = "/api/admin/v1/user-emails"
        data = {"user_id": mas_user_id, "email": email}
        resp = self.send_to_mas("POST", endpoint=endpoint, json=data)
        json_body = await self.decode_response(resp)
        if not resp.ok:
            error = f"Cannot add email {email} for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        json_report[user_id]["description"] = json_body["data"]
        return True


def format_timestamp(ts: int | None) -> str | None:
    if ts is None:
        return None
    # if ts is in ms (> 1e10), we convert to second
    if ts > 1e10:
        ts = int(ts / 1000)
    return datetime.fromtimestamp(ts, tz=ZoneInfo("Europe/Paris")).strftime(
        "%d/%m/%Y %H:%M:%S",
    )
