"""QQ preflight and explicit fixed-message smoke; no Agent is ever called."""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from websockets.asyncio.client import connect

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.probes.common import Check, emit, environment_checks
from tools.probes.rpc import ProtocolError

QQ_VARIABLES = (
    "CHATBRIDGE_QQ_APP_ID",
    "CHATBRIDGE_QQ_APP_SECRET",
    "CHATBRIDGE_QQ_C2C_OPENID",
    "CHATBRIDGE_QQ_GROUP_OPENID",
    "CHATBRIDGE_QQ_GROUP_MEMBER_OPENID",
)


def authorized_target(event, env):
    if not isinstance(event, dict) or event.get("op") != 0:
        return None
    data = event.get("d")
    if not isinstance(data, dict) or not isinstance(data.get("author"), dict):
        return None
    author, message_id = data["author"], data.get("id")
    if not isinstance(message_id, str) or not message_id:
        return None
    if event.get("t") == "C2C_MESSAGE_CREATE":
        owner = env.get("CHATBRIDGE_QQ_C2C_OPENID")
        if owner and owner == author.get("user_openid"):
            return "users", owner, message_id
    if event.get("t") == "GROUP_AT_MESSAGE_CREATE":
        group, owner = (
            env.get("CHATBRIDGE_QQ_GROUP_OPENID"),
            env.get("CHATBRIDGE_QQ_GROUP_MEMBER_OPENID"),
        )
        if (
            group
            and owner
            and group == data.get("group_openid")
            and owner == author.get("member_openid")
        ):
            return "groups", group, message_id
    return None


class GatewayState:
    def __init__(self, token):
        self.token, self.session_id, self.sequence = token, None, None
        self.awaiting_ack, self.ack_seen, self.interval = False, False, 45

    def hello(self, frame, resume=False):
        data = frame.get("d", {})
        interval = data.get("heartbeat_interval") if isinstance(data, dict) else None
        if (
            frame.get("op") != 10
            or not isinstance(interval, (int, float))
            or not 0 < interval <= 300000
        ):
            raise ProtocolError("INVALID_HELLO")
        self.interval, self.awaiting_ack = interval / 1000, False
        self.ack_seen = False
        if resume:
            if not self.session_id or self.sequence is None:
                raise ProtocolError("NO_RESUME_CONTEXT")
            return {
                "op": 6,
                "d": {
                    "token": "QQBot " + self.token,
                    "session_id": self.session_id,
                    "seq": self.sequence,
                },
            }
        return {
            "op": 2,
            "d": {"token": "QQBot " + self.token, "intents": 1 << 25, "shard": [0, 1]},
        }

    def receive(self, frame):
        if frame.get("op") == 9:
            raise ProtocolError("INVALID_SESSION")
        if frame.get("op") == 11 and self.awaiting_ack:
            self.awaiting_ack, self.ack_seen = False, True
        if frame.get("op") == 0:
            sequence = frame.get("s")
            if isinstance(sequence, int):
                self.sequence = sequence
            if frame.get("t") == "READY":
                data = frame.get("d")
                session_id = data.get("session_id") if isinstance(data, dict) else None
                if not isinstance(session_id, str) or not session_id:
                    raise ProtocolError("MISSING_SESSION_ID")
                self.session_id = session_id

    def heartbeat(self):
        if self.awaiting_ack:
            raise ProtocolError("HEARTBEAT_ACK_MISSING")
        self.awaiting_ack = True
        return {"op": 1, "d": self.sequence}


class QQApi:
    def __init__(self, client, env):
        self.client, self.env, self.token = client, env, None

    async def refresh_token(self):
        response = await self.client.post(
            "https://bots.qq.com/app/getAppAccessToken",
            json={
                "appId": self.env["CHATBRIDGE_QQ_APP_ID"],
                "clientSecret": self.env["CHATBRIDGE_QQ_APP_SECRET"],
            },
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if (
            not isinstance(token, str)
            or not token
            or int(data.get("expires_in", 0)) <= 0
        ):
            raise ProtocolError("INVALID_ACCESS_TOKEN_RESPONSE")
        self.token = token

    async def gateway(self):
        response = await self.client.get(
            "https://api.sgroup.qq.com/gateway/bot",
            headers={"Authorization": "QQBot " + self.token},
        )
        response.raise_for_status()
        url = response.json().get("url", "")
        parsed = urlparse(url)
        if (
            parsed.scheme != "wss"
            or not parsed.hostname
            or not parsed.hostname.endswith(".qq.com")
        ):
            raise ProtocolError("INVALID_GATEWAY_URL")
        return url

    async def reply(self, target):
        kind, identifier, message_id = target
        try:
            response = await self.client.post(
                f"https://api.sgroup.qq.com/v2/{kind}/{identifier}/messages",
                headers={"Authorization": "QQBot " + self.token},
                json={
                    "content": "ChatBridge M1 probe OK",
                    "msg_type": 0,
                    "msg_id": message_id,
                    "msg_seq": 1,
                },
            )
        except httpx.TransportError:
            return "uncertain"
        if response.is_success and isinstance(response.json().get("id"), str):
            return "sent"
        return "blocked"


async def live_roundtrip(env, seconds):
    checks, seen, answered = [], set(), set()
    async with httpx.AsyncClient(timeout=15) as http:
        api = QQApi(http, env)
        await api.refresh_token()
        checks.append(Check("qq_token", "pass"))
        gateway = await api.gateway()
        state = GatewayState(api.token)
        deadline = time.monotonic() + seconds
        for resume in (False, True):
            async with connect(gateway, open_timeout=15, max_size=1024 * 1024) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), 15))
                await ws.send(json.dumps(state.hello(hello, resume=resume)))
                next_heartbeat, connected = time.monotonic(), False
                while time.monotonic() < deadline:
                    now = time.monotonic()
                    if now >= next_heartbeat:
                        await ws.send(json.dumps(state.heartbeat()))
                        next_heartbeat = now + state.interval
                    try:
                        frame = json.loads(
                            await asyncio.wait_for(
                                ws.recv(), min(next_heartbeat - now, deadline - now)
                            )
                        )
                    except TimeoutError:
                        continue
                    state.receive(frame)
                    if frame.get("op") == 7:
                        raise ProtocolError("SERVER_REQUESTED_RECONNECT")
                    if frame.get("op") == 1:
                        await ws.send(json.dumps({"op": 1, "d": state.sequence}))
                    if frame.get("t") == ("RESUMED" if resume else "READY"):
                        connected = True
                        checks.append(
                            Check("qq_resume" if resume else "qq_identify", "pass")
                        )
                        if not resume:
                            break
                    target = (
                        authorized_target(frame, env) if connected and resume else None
                    )
                    if target and target not in seen and target[0] not in answered:
                        seen.add(target)
                        status = await api.reply(target)
                        checks.append(
                            Check(
                                "qq_" + target[0] + "_roundtrip",
                                "pass" if status == "sent" else "blocked",
                                status,
                            )
                        )
                        answered.add(target[0])
                    if resume and answered == {"users", "groups"} and state.ack_seen:
                        break
                if not connected:
                    checks.append(
                        Check(
                            "qq_" + ("resume" if resume else "identify"),
                            "blocked",
                            "EVENT_TIMEOUT",
                        )
                    )
                    break
        checks.append(
            Check(
                "qq_heartbeat_ack",
                "pass" if state.ack_seen else "blocked",
                "" if state.ack_seen else "ACK_NOT_OBSERVED",
            )
        )
        for kind in ("users", "groups"):
            if kind not in answered:
                checks.append(
                    Check(
                        "qq_" + kind + "_roundtrip",
                        "blocked",
                        "OWNER_TEST_MESSAGE_REQUIRED",
                    )
                )
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Send one fixed reply per configured owner context; no Agent runs",
    )
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    if not 15 <= args.seconds <= 600:
        parser.error("--seconds must be between 15 and 600")
    prerequisites = [
        Check(
            name,
            "pass" if os.environ.get(name) else "blocked",
            "" if os.environ.get(name) else "NOT_CONFIGURED",
        )
        for name in QQ_VARIABLES
    ]
    if not args.live:
        return emit(
            "preflight",
            environment_checks()
            + prerequisites
            + [Check("qq_live_roundtrip", "blocked", "LIVE_CAPTURE_REQUIRED")],
        )
    if any(c.status != "pass" for c in prerequisites):
        return emit("qq-smoke", prerequisites)
    try:
        checks = asyncio.run(live_roundtrip(os.environ, args.seconds))
    except Exception as exc:
        checks = [Check("qq_live_roundtrip", "fail", type(exc).__name__)]
    return emit("qq-smoke", checks)


if __name__ == "__main__":
    raise SystemExit(main())
