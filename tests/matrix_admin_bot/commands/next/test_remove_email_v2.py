from typing import Any
from unittest.mock import Mock

import pytest
from nio import MatrixRoom

from tests import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
)
from tests.matrix_admin_bot.commands.next import (
    USER,
    USER_EMAILS_LIST,
    USER_EMAILS_LIST_NO_DATA,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)


@pytest.mark.asyncio
async def test_remove_email() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            return mock_response_with_json(USER_EMAILS_LIST)
        if method == "DELETE" and url.endswith(
            "/api/admin/v1/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09"
        ):
            return mock_response_with_json({})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect
    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.send_file_message.assert_awaited_once()
    mocked_matrix_client.send_file_message.reset_mock()
    mocked_matrix_client.send.reset_mock()

    # 1 call to get the mas user id on MAS
    # 1 call to find if user has an email
    # 1 call to remove_email user
    check_requests_sent(
        mocked_matrix_client.client_session,
        "/users/by-username",
        "/user-emails",
        "/user-emails",
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_email_when_user_has_no_email() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        if method == "GET" and url.endswith(
            "/api/admin/v1/users/by-username/user_to_reset"
        ):
            return mock_response_with_json(USER)
        if method == "GET" and url.endswith("/api/admin/v1/user-emails"):
            # Our user has no email
            return mock_response_with_json(USER_EMAILS_LIST_NO_DATA)
        if method == "DELETE" and url.endswith(
            "/api/admin/v1/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09"
        ):
            return mock_response_with_json({})
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_failed_remove_email_when_api_in_error() -> None:
    def request_side_effect(method: str, url: str, **kwargs: Any) -> Mock:  # noqa: ARG001
        return mock_response_error(403, "Forbidden")

    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = request_side_effect

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example.org"
    )

    mocked_matrix_client.check_sent_message(
        "Couldn't remove email of the following users:"
    )

    t.cancel()


@pytest.mark.asyncio
async def test_non_local_user_remove_email() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room, USER1_ID, "!remove_email @user_to_reset:example2.org"
    )

    assert len(mocked_matrix_client.send.await_args_list) == 0
    assert len(mocked_matrix_client.send_reaction.await_args_list) == 0

    t.cancel()
