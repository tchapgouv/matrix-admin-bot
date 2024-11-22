from hashlib import sha256
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import unpaddedbase64
from nio import GetOpenIDTokenResponse, MatrixRoom

from tests import USER1_ID, OkValidator, create_fake_tchap_admin_bot


@pytest.mark.asyncio
async def test_mail_address() -> None:
    mocked_client, t = await create_fake_tchap_admin_bot(secure_validator=OkValidator())
    mocked_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )

    openid_token_resp = {
        "token_type": "Bearer",
        "matrix_server_name": "example.org",
        "expires_in": 3600,
        "access_token": "openid_access_token",
    }

    mocked_client.get_openid_token = AsyncMock(
        return_value=GetOpenIDTokenResponse.from_dict(openid_token_resp)
    )

    async def client_session_get_mock(url: str, **_kwargs: Any) -> Mock:
        if "/hash_details" in url:
            return Mock(
                ok=True, json=AsyncMock(return_value={"lookup_pepper": "pepper"})
            )
        return Mock(ok=False)

    async def client_session_post_mock(url: str, **kwargs: Any) -> Mock:
        if "/account/register" in url:
            return Mock(
                ok=True,
                json=AsyncMock(return_value={"token": "sydent_access_token"}),
            )
        if (
            "/lookup" in url
            and kwargs.get("headers", {}).get("Authorization")
            == "Bearer sydent_access_token"
        ):
            address_hash = str(
                unpaddedbase64.encode_base64(
                    sha256(b"user_to_reset@example.org email pepper").digest(),
                    urlsafe=True,
                )
            )
            return Mock(
                ok=True,
                json=AsyncMock(
                    return_value={
                        "mappings": {address_hash: "@user_to_reset:example.org"}
                    }
                ),
            )
        return Mock(ok=False)

    mocked_client.client_session = Mock(
        get=client_session_get_mock, post=client_session_post_mock
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password user_to_reset@example.org"
    )

    mocked_client.send_file_message.assert_awaited_once()
    mocked_client.send_file_message.reset_mock()

    # one call to fetch the devices, and one call to reset the password
    assert len(mocked_client.send.await_args_list) == 2
    assert "/devices" in mocked_client.send.await_args_list[0][0][1]
    assert (
        "/reset_password/@user_to_reset:example.org"
        in mocked_client.send.await_args_list[1][0][1]
    )
    mocked_client.send.reset_mock()

    t.cancel()
