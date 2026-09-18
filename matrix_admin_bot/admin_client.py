import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from aiohttp import ClientResponse
from matrix_bot.client import MatrixClient
from multidict import CIMultiDict, CIMultiDictProxy

from matrix_command_bot.util import get_localpart_from_id

logger = structlog.getLogger(__name__)

VERIFY_SSL_CERT = True


class MasAdminApiError(Exception):
    """Error returned by the MAS Admin API."""

    def __init__(self, status: int, reason: str | None, description: Any) -> None:  # noqa: ANN401
        self.status = status
        self.reason = reason
        self.description = description
        super().__init__(f"MAS Admin API error {status} {reason}: {description}")


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

    async def send_to_mas(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> ClientResponse:
        url = f"{self.base_url}" + endpoint
        if headers is None:
            headers = {}
        headers.update({"Authorization": f"Bearer {self.access_token}"})
        kwargs["headers"] = headers
        # At this point the client session should always be available
        # since the sync loop is already running.
        assert self.synapse_client.client_session  # noqa: S101
        return await self.synapse_client.client_session.request(method, url, **kwargs)

    async def send_to_synapse(
        self,
        method: str,
        endpoint: str,
        access_token: str | None = None,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> ClientResponse:
        if headers is None:
            headers = {}
        headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "matrix-admin-bot",
                "Authorization": f"Bearer {access_token or self.access_token}",
            }
        )
        return await self.synapse_client.send(
            method, endpoint, headers=headers, **kwargs
        )

    async def send_to_mas_with_retry(
        self,
        method: str,
        endpoint: str,
        max_retry: int = 5,
        **kwargs: Any,  # noqa: ANN401
    ) -> ClientResponse:
        for retry_nb in range(max_retry):
            try:
                resp = await self.send_to_mas(method, endpoint=endpoint, **kwargs)
                if resp.ok:
                    return resp
            except Exception as e:
                logger.warning("Request to MAS has failed", exc_info=e)
                # use some backoff
                await asyncio.sleep(0.5 * retry_nb)

        class FakeClientResponse(ClientResponse):
            def __init__(self, status: int, reason: str) -> None:
                self.status = status
                self.reason = reason
                # Minimal state required by the ClientResponse helpers used by
                # decode_client_response (headers/text/json).
                self._headers = CIMultiDictProxy(
                    CIMultiDict({"Content-Type": "text/plain"})
                )
                self._cache: dict[str, Any] = {}
                self._body = b""

        return FakeClientResponse(500, "Internal Server Error")

    async def decode_client_response(self, resp: ClientResponse) -> Any:  # noqa: ANN401
        if resp.headers.get("Content-Type", "").startswith("application/json") is True:
            return await resp.json()
        return await resp.text()

    async def get_paginated_data(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        page_size: int = 1000,
        with_retry: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve every item of a paginated MAS Admin API collection.

        The MAS Admin API paginates its collections with a cursor exposed in
        ``links.next``. This follows those links until the collection is
        exhausted and returns the concatenated ``data`` items.

        ``page_size`` sets the page size requested through ``page[first]``.
        It only applies to the first request: the ``next`` links returned by
        MAS already carry the full query string.

        Raises ``MasAdminApiError`` if any of the requests fails.
        """
        query = dict(params or {})
        query.setdefault("page[first]", page_size)

        items: list[dict[str, Any]] = []
        next_endpoint: str | None = endpoint
        next_params: dict[str, Any] | None = query

        while next_endpoint:
            if with_retry:
                resp = await self.send_to_mas_with_retry(
                    "GET", next_endpoint, params=next_params
                )
            else:
                resp = await self.send_to_mas("GET", next_endpoint, params=next_params)
            json_body = await self.decode_client_response(resp)
            if not resp.ok:
                raise MasAdminApiError(resp.status, resp.reason, json_body)

            items.extend(json_body.get("data", []))
            # ``links.next`` already contains the query string, so the original
            # params must not be re-applied on the next request.
            links: dict[str, Any] = json_body.get("links") or {}
            next_endpoint = links.get("next")
            if not isinstance(next_endpoint, str):
                next_endpoint = None
            next_params = None

        return items

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
        resp = await self.send_to_mas("GET", endpoint=endpoint)

        json_body = await self.decode_client_response(resp)
        if not resp.ok:
            error = f"Cannot get user from localpart {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return None
        return json_body["data"]["id"]

    async def get_users(
        self, server_name: str | None, json_report: dict[str, Any]
    ) -> set[str]:
        if server_name is None:
            return set()

        endpoint = "/api/admin/v1/users"
        params = {"filter[status]": "active"}
        try:
            users_data = await self.get_paginated_data(
                endpoint, params, with_retry=True
            )
        except MasAdminApiError as e:
            error = "Cannot get all users from MAS"
            json_report["details"]["get_users"] = {
                "error": error,
                "description": e.description,
            }
            logger.warning("%s: %s", error, f"{e.status}-{e.reason}-{e.description}")
            return set()

        return {
            f"@{user['attributes']['username']}:{server_name}"
            for user in users_data
            if user["type"] == "user"
        }

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

    async def get_all_sessions(
        self,
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        all_sessions: list[dict[str, Any]] = []
        for session_type in ["compat", "oauth2", "user", "personal"]:
            sessions = await self.get_sessions(session_type, mas_user_id, user_id)
            all_sessions.extend(sessions)
        return all_sessions

    async def get_sessions(
        self,
        session_type: str,
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        params = {
            "filter[user]": mas_user_id,
            "filter[status]": "active",
        }
        endpoint = f"/api/admin/v1/{session_type}-sessions"
        try:
            sessions = await self.get_paginated_data(endpoint, params)
        except MasAdminApiError as e:
            raise RuntimeError(
                f"Cannot get {session_type} sessions for {user_id}"
            ) from e

        if session_type == "oauth2":
            for session in sessions:
                scope_list = session.get("attributes", {}).get("scope")
                scopes: list[str] = scope_list.split() if scope_list else []
                device_id = None
                for scope in scopes:
                    for scope_prefix in [
                        "urn:matrix:client:device:",
                        "urn:matrix:org.matrix.msc2967.client:device:",
                    ]:
                        if scope.startswith(scope_prefix):
                            device_id = scope[len(scope_prefix) :]
                            break
                if device_id:
                    session["attributes"]["device_id"] = device_id

        return sessions

    async def get_compat_sessions(
        self,
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        return await self.get_sessions("compat", mas_user_id, user_id)

    async def get_user_sessions(
        self,
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        return await self.get_sessions("user", mas_user_id, user_id)

    async def get_oauth2_sessions(
        self,
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        return await self.get_sessions("oauth2", mas_user_id, user_id)

    async def get_personal_sessions(
        self,
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        return await self.get_sessions("personal", mas_user_id, user_id)

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
        resp = await self.send_to_mas("POST", endpoint=endpoint, json=data)
        if not resp.ok:
            json_body = await self.decode_client_response(resp)
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
        resp = await self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_client_response(resp)
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
        resp = await self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_client_response(resp)
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
        resp = await self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_client_response(resp)
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
        resp = await self.send_to_mas("POST", endpoint=endpoint, json=data)
        json_body = await self.decode_client_response(resp)
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
        resp = await self.send_to_mas("POST", endpoint=endpoint)
        json_body = await self.decode_client_response(resp)
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
        try:
            emails = await self.get_paginated_data(endpoint, params)
        except MasAdminApiError as e:
            if e.status == 404:
                return []
            error = f"Cannot find emails with {params} for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": e.description}
            )
            failed_user_ids.append(user_id)
            return None
        json_report[user_id]["description"] = emails
        return emails

    async def remove_email(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        user_email_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/user-emails/{user_email_id}"
        resp = await self.send_to_mas("DELETE", endpoint=endpoint)
        json_body = await self.decode_client_response(resp)
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
        resp = await self.send_to_mas("POST", endpoint=endpoint, json=data)
        json_body = await self.decode_client_response(resp)
        if not resp.ok:
            error = f"Cannot add email {email} for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
        json_report[user_id]["description"] = json_body["data"]
        return True

    async def find_upstream_oauth_links(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        mas_user_id: str,
        user_id: str,
    ) -> list[dict[str, Any]] | None:
        params = {"filter[user]": mas_user_id}
        endpoint = "/api/admin/v1/upstream-oauth-links"
        try:
            return await self.get_paginated_data(endpoint, params)
        except MasAdminApiError as e:
            if e.status == 404:
                return []
            error = f"Cannot find upstream OAuth links for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": e.description}
            )
            failed_user_ids.append(user_id)
            return None

    async def remove_upstream_oauth_link(
        self,
        json_report: dict[str, Any],
        failed_user_ids: list[str],
        link_id: str,
        user_id: str,
    ) -> bool:
        endpoint = f"/api/admin/v1/upstream-oauth-links/{link_id}"
        resp = await self.send_to_mas("DELETE", endpoint=endpoint)
        if not resp.ok:
            json_body = await self.decode_client_response(resp)
            error = f"Cannot remove upstream OAuth link {link_id} for {user_id}"
            json_report[user_id]["errors"].append(
                {"error": error, "description": json_body}
            )
            failed_user_ids.append(user_id)
            return False
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
