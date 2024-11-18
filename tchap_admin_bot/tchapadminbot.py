import base64
from hashlib import sha256
from typing import Any

import structlog
from nio import GetOpenIDTokenResponse

from matrix_admin_bot.adminbot import AdminBot, AdminBotConfig
from matrix_command_bot.util import get_server_name

logger = structlog.getLogger(__name__)


class TchapAdminBotConfig(AdminBotConfig):
    sydent: str = "http://localhost:8090"


class TchapAdminBot(AdminBot):
    def __init__(
        self,
        config: TchapAdminBotConfig,
        **extra_config: Any,  # noqa: ANN401
    ) -> None:
        self.sydent = config.sydent
        if "get_matrix_id_fct" not in extra_config:
            extra_config["get_matrix_id_fct"] = self.get_matrix_id
        super().__init__(config, **extra_config)

        self.sydent_access_token: str | None = None

    async def get_matrix_id(self, user_id: str) -> str:
        if user_id.startswith("@") and get_server_name(user_id):
            return user_id

        access_token = await self.get_sydent_access_token()
        pepper = await self.get_hash_pepper()
        if self.matrix_client.client_session and access_token and pepper:
            address_hash = str(
                base64.urlsafe_b64encode(
                    sha256(f"{user_id} email {pepper}".encode()).digest()
                )
            )
            res = await self.matrix_client.client_session.post(
                f"{self.sydent}/_matrix/identity/v2/lookup",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                json={
                    "addresses": [address_hash],
                    "algorithm": "sha256",
                    "pepper": pepper,
                },
            )
            if res.ok:
                body = await res.json()
                matrix_id = body.get("mappings", {}).get(address_hash)
                if matrix_id:
                    logger.warning(f"matrix_id {matrix_id}")
                    return matrix_id

        return user_id

    async def get_hash_pepper(self) -> str | None:
        # TODO keep a cache
        if self.matrix_client.client_session:
            res = await self.matrix_client.client_session.get(
                f"{self.sydent}/_matrix/identity/v2/hash_details",
            )
            if res.ok:
                body = await res.json()
                return body.get("lookup_pepper")
        return None

    async def get_sydent_access_token(self) -> str | None:
        if not self.sydent_access_token and self.matrix_client.client_session:
            openid_token_resp = await self.matrix_client.get_openid_token(
                self.matrix_client.user_id
            )
            if isinstance(openid_token_resp, GetOpenIDTokenResponse):
                res = await self.matrix_client.client_session.post(
                    f"{self.sydent}/_matrix/identity/v2/account/register",
                    json={
                        "token_type": openid_token_resp.token_type,
                        "matrix_server_name": openid_token_resp.matrix_server_name,
                        "expires_in": openid_token_resp.expires_in,
                        "access_token": openid_token_resp.access_token,
                    },
                )
                if res.ok:
                    body = await res.json()
                    self.sydent_access_token = body.get("token", None)

        return self.sydent_access_token


def main() -> None:
    config = TchapAdminBotConfig()
    bot = TchapAdminBot(config)
    bot.run()


if __name__ == "__main__":
    main()
