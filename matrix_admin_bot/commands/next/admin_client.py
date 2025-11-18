from typing import Any

import requests
import structlog
from aiohttp import ClientResponse
from matrix_bot.client import MatrixClient
from requests import Response

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
