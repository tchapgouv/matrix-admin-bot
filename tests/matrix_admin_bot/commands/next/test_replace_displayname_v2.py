import pytest
from nio import MatrixRoom

from tests.helper import (
    USER1_ID,
    OkValidator,
    check_requests_sent,
    create_fake_admin_bot,
    find_request,
)
from tests.matrix_admin_bot.commands.next import (
    USER,
    mock_requests,
    mock_response_error,
    mock_response_with_json,
    mock_send_response,
)

SYNAPSE_USER_ENDPOINT = "/_synapse/admin/v2/users/@user_to_reset:example.org"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "displayname_arg",
    ["My-Display Name[matrix]", "'My-Display Name[matrix]'"],
)
async def test_replace_displayname(displayname_arg: str) -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        ("GET", "/api/admin/v1/users/by-username", mock_response_with_json(USER)),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        f"!replace_displayname @user_to_reset:example.org {displayname_arg}",
    )

    # 1 call to get the mas user id on MAS
    # 1 call to change displayname on Synapse
    displayname_request = find_request(
        mocked_matrix_client.send, "PUT", SYNAPSE_USER_ENDPOINT
    )
    assert (
        displayname_request.kwargs["data"]
        == '{"displayname": "My-Display Name[matrix]"}'
    )
    check_requests_sent(mocked_matrix_client.send, SYNAPSE_USER_ENDPOINT)
    check_requests_sent(mocked_matrix_client.client_session, "/users/by-username")

    mocked_matrix_client.check_sent_file_message()

    t.cancel()


@pytest.mark.asyncio
async def test_failed_replace_displayname_when_user_not_found() -> None:
    mocked_matrix_client, _, t = await create_fake_admin_bot(validator=OkValidator())
    mocked_matrix_client.send = mock_send_response()
    mocked_matrix_client.client_session.request.side_effect = mock_requests(
        (
            "GET",
            "/api/admin/v1/users/by-username",
            mock_response_error(404, "Not found"),
        ),
    )

    room = MatrixRoom("!roomid:example.org", USER1_ID)

    await mocked_matrix_client.fake_synced_text_message(
        room,
        USER1_ID,
        "!replace_displayname @user_to_reset:example.org 'My-Display Name[matrix]'",
    )

    mocked_matrix_client.check_sent_file_message()

    # 1 call to get the mas user id on MAS
    check_requests_sent(mocked_matrix_client.client_session, "/users/by-username")

    t.cancel()
