"""Exercise replay-before-RESUMED through the real smoke loop and HTTP boundary."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from tools.probes import qqbot as qq
from tools.probes.common import exit_code
from tools.probes.rpc import ProtocolError


def run_replay(
    monkeypatch,
    *,
    replay_kind,
    resumed=True,
    second_ack=True,
    invalid=False,
    repeat_after=False,
):
    clock = SimpleNamespace(now=0, resumed=False)
    monkeypatch.setattr(qq, "time", SimpleNamespace(monotonic=lambda: clock.now))
    hello = {"op": 10, "d": {"heartbeat_interval": 45000}}
    private = {
        "op": 0,
        "s": 2,
        "t": "C2C_MESSAGE_CREATE",
        "d": {"id": "replayed-private", "author": {"user_openid": "private-owner"}},
    }
    group = {
        "op": 0,
        "s": 3,
        "t": "GROUP_AT_MESSAGE_CREATE",
        "d": {
            "id": "replayed-group",
            "group_openid": "allowed-group",
            "author": {"member_openid": "group-owner"},
        },
    }
    first = [
        hello,
        {"op": 11},
        {"op": 0, "s": 1, "t": "READY", "d": {"session_id": "fixture-session"}},
    ]
    before = (
        [private, group]
        if replay_kind == "both"
        else [private if replay_kind == "users" else group]
    )
    after = (
        [] if replay_kind == "both" else [group if replay_kind == "users" else private]
    )
    # Unauthorized events and duplicated replay frames must not cause extra replies.
    foreign = {
        "op": 0,
        "s": 2,
        "t": "C2C_MESSAGE_CREATE",
        "d": {"id": "foreign-message", "author": {"user_openid": "foreign-owner"}},
    }
    second = [hello, foreign, *before, *before]
    if invalid:
        second.append({"op": 9})
    elif resumed:
        second += [
            {"op": 0, "s": 4, "t": "RESUMED", "d": ""},
            *(before if repeat_after else []),
            *after,
        ]
    if second_ack:
        second.append({"op": 11})
    sockets = [first, second]
    replies = []

    class Socket:
        def __init__(self, frames):
            self.frames = list(frames)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def send(self, _):
            pass

        async def recv(self):
            if not self.frames:
                clock.now = 1000
                raise TimeoutError
            frame = self.frames.pop(0)
            if frame.get("t") == "RESUMED":
                clock.resumed = True
            return json.dumps(frame)

    def handler(request):
        if request.url.path == "/app/getAppAccessToken":
            return httpx.Response(
                200, json={"access_token": "fixture-token", "expires_in": 7200}
            )
        if request.url.path == "/gateway/bot":
            return httpx.Response(200, json={"url": "wss://api.bot.qq.com/websocket/"})
        # Replies must wait until this connection confirms a successful resume.
        assert clock.resumed
        replies.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"id": "fixture-reply"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        qq.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(qq, "connect", lambda *args, **kwargs: Socket(sockets.pop(0)))
    env = {
        "CHATBRIDGE_QQ_APP_ID": "fixture-app",
        "CHATBRIDGE_QQ_APP_SECRET": "fixture-secret",
        "CHATBRIDGE_QQ_C2C_OPENID": "private-owner",
        "CHATBRIDGE_QQ_GROUP_OPENID": "allowed-group",
        "CHATBRIDGE_QQ_GROUP_MEMBER_OPENID": "group-owner",
    }
    if invalid:
        with pytest.raises(ProtocolError, match="INVALID_SESSION"):
            asyncio.run(qq.live_roundtrip(env, 15))
        return None, replies
    return asyncio.run(qq.live_roundtrip(env, 15)), replies


@pytest.mark.parametrize("replay_kind", ["users", "groups", "both"])
def test_replay_before_resumed_is_replied_once_after_confirmation(
    monkeypatch, replay_kind
):
    checks, replies = run_replay(monkeypatch, replay_kind=replay_kind)
    assert exit_code(checks) == 0
    assert sorted(replies, key=lambda r: r[0]) == [
        (
            "/v2/groups/allowed-group/messages",
            {
                "content": "ChatBridge M1 probe OK",
                "msg_type": 0,
                "msg_id": "replayed-group",
                "msg_seq": 1,
            },
        ),
        (
            "/v2/users/private-owner/messages",
            {
                "content": "ChatBridge M1 probe OK",
                "msg_type": 0,
                "msg_id": "replayed-private",
                "msg_seq": 1,
            },
        ),
    ]


def test_replay_without_resume_confirmation_never_sends(monkeypatch):
    checks, replies = run_replay(monkeypatch, replay_kind="both", resumed=False)
    assert exit_code(checks) == 2
    assert replies == []
    assert any(
        check.name == "qq_resume" and check.status == "blocked" for check in checks
    )


def test_rejected_resume_does_not_send_buffered_messages(monkeypatch):
    _, replies = run_replay(monkeypatch, replay_kind="both", invalid=True)
    assert replies == []


def test_replay_cannot_reuse_ack_from_previous_connection(monkeypatch):
    checks, replies = run_replay(monkeypatch, replay_kind="both", second_ack=False)
    assert len(replies) == 2
    assert exit_code(checks) == 2
    assert (
        next(check for check in checks if check.name == "qq_heartbeat_ack").status
        == "blocked"
    )


def test_replay_repeated_after_confirmation_is_not_sent_twice(monkeypatch):
    checks, replies = run_replay(monkeypatch, replay_kind="both", repeat_after=True)
    assert exit_code(checks) == 0
    assert len(replies) == 2
