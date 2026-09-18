from unittest.mock import AsyncMock, Mock

import pytest

from matrix_admin_bot.admin_client import AdminClient, MasAdminApiError
from tests.matrix_admin_bot.commands.next import (
    mock_response_error,
    mock_response_with_json,
)


def make_admin_client() -> tuple[AdminClient, AsyncMock]:
    client_session = Mock()
    request = AsyncMock()
    client_session.request = request
    synapse_client = Mock()
    synapse_client.client_session = client_session
    admin_client = AdminClient(synapse_client, "http://mas.example.org", "token")
    return admin_client, request


@pytest.mark.asyncio
async def test_get_paginated_data_follows_next_links() -> None:
    admin_client, request = make_admin_client()

    page1 = {
        "meta": {"count": 2},
        "data": [{"id": "a"}],
        "links": {"next": "/api/admin/v1/users?page[after]=a&page[first]=1"},
    }
    page2 = {"meta": {"count": 2}, "data": [{"id": "b"}], "links": {}}
    request.side_effect = [
        mock_response_with_json(page1),
        mock_response_with_json(page2),
    ]

    data = await admin_client.get_paginated_data(
        "/api/admin/v1/users", {"filter[status]": "active"}
    )

    assert data == [{"id": "a"}, {"id": "b"}]

    first_call, second_call = request.await_args_list
    # The first request carries the filters and the page size.
    assert first_call.args[0] == "GET"
    assert first_call.args[1] == "http://mas.example.org/api/admin/v1/users"
    assert first_call.kwargs["params"] == {
        "filter[status]": "active",
        "page[first]": 1000,
    }
    # ``links.next`` is used as-is, without re-applying the original params.
    assert second_call.args[1] == (
        "http://mas.example.org/api/admin/v1/users?page[after]=a&page[first]=1"
    )
    assert second_call.kwargs["params"] is None


@pytest.mark.asyncio
async def test_get_paginated_data_raises_on_error() -> None:
    admin_client, request = make_admin_client()
    request.side_effect = [mock_response_error(403, "Forbidden")]

    with pytest.raises(MasAdminApiError) as exc_info:
        await admin_client.get_paginated_data("/api/admin/v1/users")

    assert exc_info.value.status == 403
