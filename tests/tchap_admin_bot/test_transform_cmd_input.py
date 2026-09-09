from hashlib import sha256
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import unpaddedbase64
from nio import GetOpenIDTokenResponse, MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    COMPAT_SESSIONS_LIST,
    OAUTH2_SESSIONS_LIST,
    USER,
    USER_SESSIONS_LIST,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_mail_address() -> None:  # noqa: C901
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001,PLR0911
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "POST" and url.endswith(
            "/api/admin/v1/users/01040G2081040G2081040G2081/set-password"
        ):
            return mock_response_with_json(USER)
        if method == "POST" and url.endswith(
            "/api/admin/v1/users/01040G2081040G2081040G2081/kill-sessions"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/compat-sessions"):
            return mock_response_with_json(COMPAT_SESSIONS_LIST)
        if method == "GET" and url.endswith("/api/admin/v1/oauth2-sessions"):
            return mock_response_with_json(OAUTH2_SESSIONS_LIST)
        if method == "GET" and url.endswith("/api/admin/v1/user-sessions"):
            return mock_response_with_json(USER_SESSIONS_LIST)
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    openid_token_resp = {
        "token_type": "Bearer",
        "matrix_server_name": "example.org",
        "expires_in": 3600,
        "access_token": "openid_access_token",
    }

    mocked_matrix_client.get_openid_token = AsyncMock(
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

    mocked_matrix_client.client_session.get.side_effect = client_session_get_mock
    mocked_matrix_client.client_session.post.side_effect = client_session_post_mock

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password user_to_reset@example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # 1 call to fetch the devices on synapse
    check_requests_sent(mocked_matrix_client.send, "/devices")
    # 3 calls to the identity server to resolve the email
    # 1 call to get the mas user id on MAS
    # 3 calls to get each session type
    # 1 call to reset the password
    # 1 call to kill sessions
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/_matrix/identity/v2/account/register",
        "/_matrix/identity/v2/hash_details",
        "/_matrix/identity/v2/lookup",
        "/users/by-username",
        "/compat-sessions",
        "/user-sessions",
        "/oauth2-sessions",
        "/set-password",
        "/kill-sessions",
    )

    t.cancel()
