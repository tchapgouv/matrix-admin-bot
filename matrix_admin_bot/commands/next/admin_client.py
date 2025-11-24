from typing import Any

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

    async def decode_response(self, resp: Response) -> Any:  # noqa: ANN401
        if resp.headers.get("Content-Type", "").startswith("application/json") is True:
            return resp.json()
        return resp.text

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
                json_report[user_id]["compat-sessions"] = sessions
                logger.debug(
                    "Compat-Sessions : %s", json_report[user_id]["compat-sessions"]
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
                json_report[user_id]["user-sessions"] = sessions
                logger.debug(
                    "User-Sessions : %s", json_report[user_id]["user-sessions"]
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
                json_report[user_id]["oauth2-sessions"] = sessions
                logger.debug(
                    "OAuth2-Sessions : %s", json_report[user_id]["oauth2-sessions"]
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

def check_if_mas_enabled(homeserver: str | None) -> bool:
    if homeserver:
        url = f"{homeserver}/.well-known/matrix/client"
        try:
            resp = requests.request(
                method="GET", url=url, verify=VERIFY_SSL_CERT, timeout=10
            )
            if resp.ok:
                json_body = resp.json()
                return (
                    "org.matrix.msc2965.authentication" in json_body
                    or "m.authentication" in json_body
                )
        except Exception:
            logger.exception("Cannot request %s", url)
    return False
