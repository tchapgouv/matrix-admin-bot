from typing import Any
from unittest.mock import Mock

USER_EMAIL = {
    "data": {
        "type": "user-email",
        "id": "01040G2081040G2081040G2081",
        "attributes": {
            "created_at": "1970-01-01T00:00:00Z",
            "user_id": "02081040G2081040G2081040G2",
            "email": "user_to_reset@domain.tld",
        },
        "links": {"self": "/api/admin/v1/user-emails/01040G2081040G2081040G2081"},
    },
    "links": {"self": "/api/admin/v1/user-emails/01040G2081040G2081040G2081"},
}
USER_EMAILS_LIST = {
    "meta": {"count": 1},
    "data": [
        {
            "type": "user-email",
            "id": "01K5R30ZEENQQCR9ZPQY9KYP09",
            "attributes": {
                "created_at": "2025-09-22T06:50:50.190780Z",
                "user_id": "01K5EMRC1GTYJF19ZAHM5R9Y9H",
                "email": "user_to_reset@domain.tld",
            },
            "links": {"self": "/api/admin/v1/user-emails/01K5R30ZEENQQCR9ZPQY9KYP09"},
            "meta": {"page": {"cursor": "01K5R30ZEENQQCR9ZPQY9KYP09"}},
        }
    ],
    "links": {
        "self": "/api/admin/v1/user-emails?filter[email]=user_to_reset@domain.tld"
        "&page[first]=10",
        "first": "/api/admin/v1/user-emails?filter[email]=user_to_reset@domain.tld"
        "&page[first]=10",
        "last": "/api/admin/v1/user-emails?filter[email]=user_to_reset@domain.tld"
        "&page[last]=10",
    },
}
USER_EMAILS_LIST_NO_DATA: dict[str, Any] = {
    "meta": {"count": 0},
    "data": [],
    "links": {
        "self": "/api/admin/v1/user-emails?filter[email]=user_to_reset@domain.tld"
        "&page[first]=10",
        "first": "/api/admin/v1/user-emails?filter[email]=user_to_reset@domain.tld"
        "&page[first]=10",
        "last": "/api/admin/v1/user-emails?filter[email]=user_to_reset@domain.tld"
        "&page[last]=10",
    },
}

USER = {
    "data": {
        "type": "user",
        "id": "01040G2081040G2081040G2081",
        "attributes": {
            "username": "user_to_reset",
            "created_at": "1970-01-01T00:00:00Z",
            "locked_at": None,
            "deactivated_at": None,
            "admin": False,
            "legacy_guest": False,
        },
        "links": {"self": "/api/admin/v1/users/01040G2081040G2081040G2081"},
    },
    "links": {"self": "/api/admin/v1/users/by-username/user_to_reset"},
}

COMPAT_SESSIONS_LIST = {
    "meta": {"count": 42},
    "data": [
        {
            "type": "compat-session",
            "id": "01040G2081040G2081040G2081",
            "attributes": {
                "user_id": "01040G2081040G2081040G2081",
                "device_id": "AABBCCDDEE",
                "user_session_id": "0H248H248H248H248H248H248H",
                "redirect_uri": "https://example.com/redirect",
                "created_at": "1970-01-01T00:00:00Z",
                "user_agent": "Mozilla/5.0",
                "last_active_at": "1970-01-01T00:00:00Z",
                "last_active_ip": "1.2.3.4",
                "finished_at": "null",
                "human_name": "Laptop",
            },
            "links": {
                "self": "/api/admin/v1/compat-sessions/01040G2081040G2081040G2081"
            },
            "meta": {"page": {"cursor": "01040G2081040G2081040G2081"}},
        },
        {
            "type": "compat-session",
            "id": "02081040G2081040G2081040G2",
            "attributes": {
                "user_id": "01040G2081040G2081040G2081",
                "device_id": "FFGGHHIIJJ",
                "user_session_id": "0J289144GJ289144GJ289144GJ",
                "redirect_uri": "null",
                "created_at": "1970-01-01T00:00:00Z",
                "user_agent": "Mozilla/5.0",
                "last_active_at": "1970-01-01T00:00:00Z",
                "last_active_ip": "1.2.3.4",
                "finished_at": "1970-01-01T00:00:00Z",
                "human_name": "null",
            },
            "links": {
                "self": "/api/admin/v1/compat-sessions/02081040G2081040G2081040G2"
            },
            "meta": {"page": {"cursor": "02081040G2081040G2081040G2"}},
        },
        {
            "type": "compat-session",
            "id": "030C1G60R30C1G60R30C1G60R3",
            "attributes": {
                "user_id": "01040G2081040G2081040G2081",
                "device_id": "null",
                "user_session_id": "null",
                "redirect_uri": "null",
                "created_at": "1970-01-01T00:00:00Z",
                "user_agent": "null",
                "last_active_at": "null",
                "last_active_ip": "null",
                "finished_at": "null",
                "human_name": "null",
            },
            "links": {
                "self": "/api/admin/v1/compat-sessions/030C1G60R30C1G60R30C1G60R3"
            },
            "meta": {"page": {"cursor": "030C1G60R30C1G60R30C1G60R3"}},
        },
    ],
    "links": {
        "self": "/api/admin/v1/compat-sessions?page[first]=3",
        "first": "/api/admin/v1/compat-sessions?page[first]=3",
        "last": "/api/admin/v1/compat-sessions?page[last]=3",
        "next": "/api/admin/v1/compat-sessions?page[after]=030C1G60R30C1G60R30C1G60R3"
        "&page[first]=3",
    },
}

OAUTH2_SESSIONS_LIST = {
    "meta": {"count": 42},
    "data": [
        {
            "type": "oauth2-session",
            "id": "01040G2081040G2081040G2081",
            "attributes": {
                "created_at": "1970-01-01T00:00:00Z",
                "finished_at": "null",
                "user_id": "02081040G2081040G2081040G2",
                "user_session_id": "030C1G60R30C1G60R30C1G60R3",
                "client_id": "040G2081040G2081040G208104",
                "scope": "openid",
                "user_agent": "Mozilla/5.0",
                "last_active_at": "1970-01-01T00:00:00Z",
                "last_active_ip": "127.0.0.1",
                "human_name": "Laptop",
            },
            "links": {
                "self": "/api/admin/v1/oauth2-sessions/01040G2081040G2081040G2081"
            },
            "meta": {"page": {"cursor": "01040G2081040G2081040G2081"}},
        },
        {
            "type": "oauth2-session",
            "id": "02081040G2081040G2081040G2",
            "attributes": {
                "created_at": "1970-01-01T00:00:00Z",
                "finished_at": "null",
                "user_id": "null",
                "user_session_id": "null",
                "client_id": "050M2GA1850M2GA1850M2GA185",
                "scope": "urn:mas:admin",
                "user_agent": "null",
                "last_active_at": "null",
                "last_active_ip": "null",
                "human_name": "null",
            },
            "links": {
                "self": "/api/admin/v1/oauth2-sessions/02081040G2081040G2081040G2"
            },
            "meta": {"page": {"cursor": "02081040G2081040G2081040G2"}},
        },
        {
            "type": "oauth2-session",
            "id": "030C1G60R30C1G60R30C1G60R3",
            "attributes": {
                "created_at": "1970-01-01T00:00:00Z",
                "finished_at": "1970-01-01T00:00:00Z",
                "user_id": "040G2081040G2081040G208104",
                "user_session_id": "050M2GA1850M2GA1850M2GA185",
                "client_id": "060R30C1G60R30C1G60R30C1G6",
                "scope": "urn:matrix:client:api:*",
                "user_agent": "Mozilla/5.0",
                "last_active_at": "1970-01-01T00:00:00Z",
                "last_active_ip": "127.0.0.1",
                "human_name": "null",
            },
            "links": {
                "self": "/api/admin/v1/oauth2-sessions/030C1G60R30C1G60R30C1G60R3"
            },
            "meta": {"page": {"cursor": "030C1G60R30C1G60R30C1G60R3"}},
        },
    ],
    "links": {
        "self": "/api/admin/v1/oauth2-sessions?page[first]=3",
        "first": "/api/admin/v1/oauth2-sessions?page[first]=3",
        "last": "/api/admin/v1/oauth2-sessions?page[last]=3",
        "next": "/api/admin/v1/oauth2-sessions?page[after]=030C1G60R30C1G60R30C1G60R3"
        "&page[first]=3",
    },
}

USER_SESSIONS_LIST = {
    "meta": {"count": 42},
    "data": [
        {
            "type": "user-session",
            "id": "01040G2081040G2081040G2081",
            "attributes": {
                "created_at": "1970-01-01T00:00:00Z",
                "finished_at": "null",
                "user_id": "02081040G2081040G2081040G2",
                "user_agent": "Mozilla/5.0",
                "last_active_at": "1970-01-01T00:00:00Z",
                "last_active_ip": "127.0.0.1",
            },
            "links": {"self": "/api/admin/v1/user-sessions/01040G2081040G2081040G2081"},
            "meta": {"page": {"cursor": "01040G2081040G2081040G2081"}},
        },
        {
            "type": "user-session",
            "id": "02081040G2081040G2081040G2",
            "attributes": {
                "created_at": "1970-01-01T00:00:00Z",
                "finished_at": "null",
                "user_id": "030C1G60R30C1G60R30C1G60R3",
                "user_agent": "null",
                "last_active_at": "null",
                "last_active_ip": "null",
            },
            "links": {"self": "/api/admin/v1/user-sessions/02081040G2081040G2081040G2"},
            "meta": {"page": {"cursor": "02081040G2081040G2081040G2"}},
        },
        {
            "type": "user-session",
            "id": "030C1G60R30C1G60R30C1G60R3",
            "attributes": {
                "created_at": "1970-01-01T00:00:00Z",
                "finished_at": "1970-01-01T00:00:00Z",
                "user_id": "040G2081040G2081040G208104",
                "user_agent": "Mozilla/5.0",
                "last_active_at": "1970-01-01T00:00:00Z",
                "last_active_ip": "127.0.0.1",
            },
            "links": {"self": "/api/admin/v1/user-sessions/030C1G60R30C1G60R30C1G60R3"},
            "meta": {"page": {"cursor": "030C1G60R30C1G60R30C1G60R3"}},
        },
    ],
    "links": {
        "self": "/api/admin/v1/user-sessions?page[first]=3",
        "first": "/api/admin/v1/user-sessions?page[first]=3",
        "last": "/api/admin/v1/user-sessions?page[last]=3",
        "next": "/api/admin/v1/user-sessions?page[after]=030C1G60R30C1G60R30C1G60R3"
        "&page[first]=3",
    },
}


def mock_response_error(status_code: int, text: str) -> Mock:
    return Mock(
        ok=False,
        status_code=status_code,
        text=text,
    )


def mock_response_with_json(json: dict[str, Any]) -> Mock:
    return Mock(
        ok=True,
        headers={
            "Content-Type": "application/json",
        },
        json=Mock(return_value=json),
    )
