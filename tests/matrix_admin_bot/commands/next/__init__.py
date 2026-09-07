from typing import Any
from unittest.mock import AsyncMock, Mock

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
                "scope": "urn:matrix:client:api:* urn:matrix:org.matrix.msc2967.client:device:QWERTYXYZ",  # noqa: E501
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

PERSONAL_SESSIONS_LIST = {
    "meta": {"count": 3},
    "data": [
        {
            "type": "personal-session",
            "id": "01FSHN9AG0AJ6AC5HQ9X6H4RP4",
            "attributes": {
                "created_at": "2022-01-16T13:00:00Z",
                "revoked_at": "null",
                "owner_user_id": "01FSHN9AG0MZAA6S4AF7CTV32E",
                "owner_client_id": "null",
                "actor_user_id": "01FSHN9AG0MZAA6S4AF7CTV32E",
                "human_name": "Alice's Development Token",
                "scope": "openid urn:matrix:org.matrix.msc2967.client:api:*",
                "last_active_at": "2022-01-16T15:30:00Z",
                "last_active_ip": "192.168.1.100",
                "expires_at": "null",
            },
            "links": {
                "self": "/api/admin/v1/personal-sessions/01FSHN9AG0AJ6AC5HQ9X6H4RP4"
            },
            "meta": {"page": {"cursor": "01FSHN9AG0AJ6AC5HQ9X6H4RP4"}},
        },
        {
            "type": "personal-session",
            "id": "01FSHN9AG0BJ6AC5HQ9X6H4RP5",
            "attributes": {
                "created_at": "2022-01-16T13:01:00Z",
                "revoked_at": "2022-01-16T16:20:00Z",
                "owner_user_id": "01FSHN9AG0NZAA6S4AF7CTV32F",
                "owner_client_id": "null",
                "actor_user_id": "01FSHN9AG0NZAA6S4AF7CTV32F",
                "human_name": "Bob's Mobile App",
                "scope": "openid",
                "last_active_at": "2022-01-16T16:03:20Z",
                "last_active_ip": "10.0.0.50",
                "expires_at": "null",
            },
            "links": {
                "self": "/api/admin/v1/personal-sessions/01FSHN9AG0BJ6AC5HQ9X6H4RP5"
            },
            "meta": {"page": {"cursor": "01FSHN9AG0BJ6AC5HQ9X6H4RP5"}},
        },
        {
            "type": "personal-session",
            "id": "01FSHN9AG0CJ6AC5HQ9X6H4RP6",
            "attributes": {
                "created_at": "2022-01-16T13:02:00Z",
                "revoked_at": "null",
                "owner_user_id": "null",
                "owner_client_id": "01FSHN9AG0DJ6AC5HQ9X6H4RP7",
                "actor_user_id": "01FSHN9AG0MZAA6S4AF7CTV32E",
                "human_name": "CI/CD Pipeline Token",
                "scope": "openid urn:mas:admin",
                "last_active_at": "2022-01-16T15:46:40Z",
                "last_active_ip": "203.0.113.10",
                "expires_at": "2022-01-24T04:36:40Z",
            },
            "links": {
                "self": "/api/admin/v1/personal-sessions/01FSHN9AG0CJ6AC5HQ9X6H4RP6"
            },
            "meta": {"page": {"cursor": "01FSHN9AG0CJ6AC5HQ9X6H4RP6"}},
        },
    ],
    "links": {
        "self": "/api/admin/v1/personal-sessions?page[first]=3",
        "first": "/api/admin/v1/personal-sessions?page[first]=3",
        "last": "/api/admin/v1/personal-sessions?page[last]=3",
        "next": "/api/admin/v1/personal-sessions?page[after]=01FSHN9AG0CJ6AC5HQ9X6H4RP6&page[first]=3",  # noqa: E501
    },
}

USER_SYNAPSE = {
    "name": "@user:example.com",
    "displayname": "User",
    "threepids": [
        {
            "medium": "email",
            "address": "<user_mail_1>",
            "added_at": 1586458409743,
            "validated_at": 1586458409743,
        },
        {
            "medium": "email",
            "address": "<user_mail_2>",
            "added_at": 1586458409743,
            "validated_at": 1586458409743,
        },
    ],
    "avatar_url": "<avatar_url>",
    "is_guest": 0,
    "admin": 0,
    "deactivated": 0,
    "erased": "false",
    "shadow_banned": 0,
    "creation_ts": 1560432506,
    "last_seen_ts": 1781554015393,
    "appservice_id": "null",
    "consent_server_notice_sent": "null",
    "consent_version": "null",
    "consent_ts": "null",
    "external_ids": [
        {"auth_provider": "<provider1>", "external_id": "<user_id_provider_1>"},
        {"auth_provider": "<provider2>", "external_id": "<user_id_provider_2>"},
    ],
    "user_type": "null",
    "locked": "false",
    "suspended": "false",
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


def async_mock_response_with_json(json: dict[str, Any]) -> Mock:
    return Mock(
        ok=True,
        headers={
            "Content-Type": "application/json",
        },
        json=AsyncMock(return_value=json),
    )
