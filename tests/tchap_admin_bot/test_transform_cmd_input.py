from hashlib import sha256
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import unpaddedbase64
from nio import GetOpenIDTokenResponse, MatrixRoom

from tests import USER1_ID, OkValidator, create_fake_tchap_admin_bot, create_fake_admin_bot_with_mas_enabled
from tests.matrix_admin_bot.commands.next import mock_response_error, mock_response_with_json, USER, \
    COMPAT_SESSIONS_LIST, OAUTH2_SESSIONS_LIST, USER_SESSIONS_LIST


@pytest.mark.asyncio
async def test_mail_address() -> None:

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

    (
        mocked_matrix_client,
        mock_admin_client,
        t,
    ) = await create_fake_admin_bot_with_mas_enabled(validator=OkValidator())
    mocked_matrix_client.send = AsyncMock(
        return_value=Mock(ok=True, json=AsyncMock(return_value={}))
    )
    mock_admin_client.session.request.side_effect = Mock(
        side_effect=request_side_effect
    )

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

    mocked_matrix_client.client_session = Mock(
        get=client_session_get_mock, post=client_session_post_mock
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!reset_password user_to_reset@example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()

    # 1 call to fetch the devices on synapse
    assert len(mocked_matrix_client.send.await_args_list) == 1
    assert "/devices" in mocked_matrix_client.send.await_args_list[0][0][1]
    mocked_matrix_client.send.reset_mock()
    # 1 call to get the mas user id on MAS
    # 3 calls to get each session type
    # 1 call to reset the password
    # 1 call to kill sessions
    assert len(mock_admin_client.session.request.call_args_list) == 6  # type: ignore[reportUnknownArgumentType]
    assert (
        "/users/by-username"
        in mock_admin_client.session.request.call_args_list[0][0][1]
    )
    assert (
        "/compat-sessions" in mock_admin_client.session.request.call_args_list[1][0][1]
    )
    assert "/user-sessions" in mock_admin_client.session.request.call_args_list[2][0][1]
    assert (
        "/oauth2-sessions" in mock_admin_client.session.request.call_args_list[3][0][1]
    )
    assert "/set-password" in mock_admin_client.session.request.call_args_list[4][0][1]
    assert "/kill-sessions" in mock_admin_client.session.request.call_args_list[5][0][1]
    mock_admin_client.session.request.reset_mock()

    t.cancel()
