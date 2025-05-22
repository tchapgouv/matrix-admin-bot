import logging
from hashlib import sha256
from typing import Any

import structlog
import unpaddedbase64
from nio import GetOpenIDTokenResponse

from matrix_admin_bot.adminbot import AdminBot, AdminBotConfig
from matrix_command_bot.command import ICommand
from matrix_command_bot.util import get_server_name

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
logger = structlog.getLogger(__name__)


class TchapAdminBotConfig(AdminBotConfig):
    log_level: str = "INFO"
    identity_server: str = "http://localhost:8090"


class TchapAdminBot(AdminBot):
    def __init__(
        self,
        config: TchapAdminBotConfig,
        **extra_config: Any,  # noqa: ANN401
    ) -> None:
        self.identity_server = config.identity_server
        if "transform_cmd_input_fct" not in extra_config:
            extra_config["transform_cmd_input_fct"] = self.transform_cmd_input
        super().__init__(config, **extra_config)

        self.identity_server_access_token: str | None = None

    async def transform_cmd_input(
        self, _command: type[ICommand], cmd_input: list[str]
    ) -> list[str]:
        potential_emails = filter(
            lambda user_id: not (user_id.startswith("@") and get_server_name(user_id)),
            cmd_input,
        )

        email_to_mxid_map: dict[str | None, Any] = {}

        access_token = await self.get_identity_server_access_token()
        pepper = await self.get_hash_pepper()
        if self.matrix_client.client_session and access_token and pepper:

            def hash_email(email: str) -> str:
                return str(
                    unpaddedbase64.encode_base64(
                        sha256(f"{email} email {pepper}".encode()).digest(),
                        urlsafe=True,
                    )
                )

            address_hash_to_email_map = {
                hash_email(email): email for email in potential_emails
            }
            res = await self.matrix_client.client_session.post(
                f"{self.identity_server}/_matrix/identity/v2/lookup",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                json={
                    "addresses": list(address_hash_to_email_map.keys()),
                    "algorithm": "sha256",
                    "pepper": pepper,
                },
            )
            if res.ok:
                body = await res.json()
                address_hash_to_mxid_map: dict[str, str] = body.get("mappings", {})
                email_to_mxid_map = {
                    address_hash_to_email_map.get(address_hash): mxid
                    for address_hash, mxid in address_hash_to_mxid_map.items()
                }
            else:
                logger.warning(
                    "Error when doing the lookup", emails=potential_emails, result=res
                )

        return [email_to_mxid_map.get(user_id, user_id) for user_id in cmd_input]

    async def get_hash_pepper(self) -> str | None:
        if self.matrix_client.client_session and self.identity_server_access_token:
            res = await self.matrix_client.client_session.get(
                f"{self.identity_server}/_matrix/identity/v2/hash_details",
                headers={
                    "Authorization": f"Bearer {self.identity_server_access_token}",
                },
            )
            if res.ok:
                body = await res.json()
                return body.get("lookup_pepper")
            logger.warning("Error when getting the lookup pepper", result=res)

        return None

    async def get_identity_server_access_token(self) -> str | None:
        if not self.identity_server_access_token and self.matrix_client.client_session:
            openid_token_resp = await self.matrix_client.get_openid_token(
                self.matrix_client.user_id
            )
            if isinstance(openid_token_resp, GetOpenIDTokenResponse):
                res = await self.matrix_client.client_session.post(
                    f"{self.identity_server}/_matrix/identity/v2/account/register",
                    json={
                        "token_type": openid_token_resp.token_type,
                        "matrix_server_name": openid_token_resp.matrix_server_name,
                        "expires_in": openid_token_resp.expires_in,
                        "access_token": openid_token_resp.access_token,
                    },
                )
                if res.ok:
                    body = await res.json()
                    self.identity_server_access_token = body.get("token", None)
                else:
                    logger.warning(
                        "Error when getting an access token from ther identity server",
                        result=res,
                    )
            else:
                logger.warning(
                    "Error when getting the OpenID token from the homeserver",
                    result=openid_token_resp,
                )

        return self.identity_server_access_token


def main() -> None:
    config = TchapAdminBotConfig()
    bot = TchapAdminBot(config)
    bot.run()


if __name__ == "__main__":
    main()
