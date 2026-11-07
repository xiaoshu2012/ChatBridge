"""Catch wrong Identify/Resume state, lost heartbeat ACK and unsafe duplicate reply."""

import asyncio
import json

import httpx
import pytest

from tools.probes.qqbot import GatewayState, QQApi
from tools.probes.rpc import ProtocolError


def test_gateway_identify_resume_and_heartbeat():
    state = GatewayState("fixture-token")
    assert state.hello({"op": 10, "d": {"heartbeat_interval": 45000}}) == {
        "op": 2,
        "d": {"token": "QQBot fixture-token", "intents": 33554432, "shard": [0, 1]},
    }
    state.receive(
        {"op": 0, "s": 3, "t": "READY", "d": {"session_id": "fixture-session"}}
    )
    assert state.heartbeat() == {"op": 1, "d": 3}
    with pytest.raises(ProtocolError):
        state.heartbeat()
    state.receive({"op": 11})
    assert state.heartbeat() == {"op": 1, "d": 3}
    assert state.hello({"op": 10, "d": {"heartbeat_interval": 45000}}, resume=True) == {
        "op": 6,
        "d": {
            "token": "QQBot fixture-token",
            "session_id": "fixture-session",
            "seq": 3,
        },
    }


def test_gateway_requires_real_ready_and_resume_success():
    state = GatewayState("fixture-token")
    with pytest.raises(ProtocolError):
        state.hello({"op": 10, "d": {"heartbeat_interval": 45000}}, resume=True)
    with pytest.raises(ProtocolError):
        state.receive({"op": 9})
    with pytest.raises(ProtocolError):
        state.hello({"op": 10, "d": {"heartbeat_interval": 0}})


def test_qq_api_uses_token_auth_and_same_passive_reply_context():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/app/getAppAccessToken":
            return httpx.Response(
                200, json={"access_token": "fixture-token", "expires_in": "7200"}
            )
        if request.url.path == "/gateway/bot":
            assert request.headers["Authorization"] == "QQBot fixture-token"
            return httpx.Response(200, json={"url": "wss://api.bot.qq.com/websocket/"})
        assert request.url.path == "/v2/users/fixture-owner/messages"
        assert json.loads(request.content) == {
            "content": "ChatBridge M1 probe OK",
            "msg_type": 0,
            "msg_id": "fixture-message",
            "msg_seq": 1,
        }
        return httpx.Response(200, json={"id": "fixture-reply"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            api = QQApi(
                client,
                {
                    "CHATBRIDGE_QQ_APP_ID": "fixture-app",
                    "CHATBRIDGE_QQ_APP_SECRET": "fixture-secret",
                },
            )
            await api.refresh_token()
            assert await api.gateway() == "wss://api.bot.qq.com/websocket/"
            assert (
                await api.reply(("users", "fixture-owner", "fixture-message")) == "sent"
            )

    asyncio.run(run())
    assert len(seen) == 3


def test_qq_uncertain_send_is_not_retried():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("fixture timeout with secret text")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            api = QQApi(client, {})
            api.token = "fixture-token"
            assert (
                await api.reply(("groups", "fixture-group", "fixture-message"))
                == "uncertain"
            )

    asyncio.run(run())
    assert calls == 1


def test_unsolicited_ack_does_not_count_as_a_heartbeat_response():
    state = GatewayState("fixture-token")
    state.hello({"op": 10, "d": {"heartbeat_interval": 45000}})
    state.receive({"op": 11})
    assert state.ack_seen is False


@pytest.mark.parametrize(("second_ack", "want_exit"), [(False, 2), (True, 0)])
def test_full_roundtrip_requires_ack_from_resumed_connection(
    monkeypatch, second_ack, want_exit
):
    from types import SimpleNamespace

    import tools.probes.qqbot as qq
    from tools.probes.common import exit_code

    clock = SimpleNamespace(now=0)
    monkeypatch.setattr(qq, "time", SimpleNamespace(monotonic=lambda: clock.now))
    hello = {"op": 10, "d": {"heartbeat_interval": 45000}}
    first = [
        hello,
        {"op": 11},
        {"op": 0, "s": 1, "t": "READY", "d": {"session_id": "fixture-session"}},
    ]
    second = [
        hello,
        {"op": 0, "s": 2, "t": "RESUMED", "d": ""},
        {
            "op": 0,
            "s": 3,
            "t": "C2C_MESSAGE_CREATE",
            "d": {"id": "fixture-c2c", "author": {"user_openid": "private-owner"}},
        },
        {
            "op": 0,
            "s": 4,
            "t": "GROUP_AT_MESSAGE_CREATE",
            "d": {
                "id": "fixture-group",
                "group_openid": "allowed-group",
                "author": {"member_openid": "group-owner"},
            },
        },
    ]
    if second_ack:
        second.append({"op": 11})
    sockets = [first, second]

    class Socket:
        def __init__(self, frames):
            self.frames = list(frames)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def send(self, frame):
            pass

        async def recv(self):
            if self.frames:
                return json.dumps(self.frames.pop(0))
            clock.now = 1000
            raise TimeoutError

    class Api:
        token = "fixture-token"

        def __init__(self, *_):
            pass

        async def refresh_token(self):
            pass

        async def gateway(self):
            return "wss://api.bot.qq.com/websocket/"

        async def reply(self, target):
            return "sent"

    monkeypatch.setattr(qq, "connect", lambda *args, **kwargs: Socket(sockets.pop(0)))
    monkeypatch.setattr(qq, "QQApi", Api)
    env = {
        "CHATBRIDGE_QQ_C2C_OPENID": "private-owner",
        "CHATBRIDGE_QQ_GROUP_OPENID": "allowed-group",
        "CHATBRIDGE_QQ_GROUP_MEMBER_OPENID": "group-owner",
    }
    result = asyncio.run(qq.live_roundtrip(env, 15))
    assert exit_code(result) == want_exit
    ack = next(check for check in result if check.name == "qq_heartbeat_ack")
    assert ack.status == ("pass" if second_ack else "blocked")
