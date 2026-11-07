"""Catch broken framing, leaked stderr, lost errors and unsafe server requests."""

import asyncio
import sys

import pytest

from tools.probes.rpc import JsonLines, ProtocolError, RpcClient, RpcError


def test_fragmented_utf8_and_multiple_frames():
    decoder = JsonLines()
    wire = '{"method":"future/event","params":{"text":"中文"}}\n{"id":1,"result":{}}\n'.encode()
    split = wire.index("中".encode()) + 1
    assert decoder.feed(wire[:split]) == []
    assert decoder.feed(wire[split:]) == [
        {"method": "future/event", "params": {"text": "中文"}},
        {"id": 1, "result": {}},
    ]
    decoder.finish()


@pytest.mark.parametrize(
    "wire", [b"not json\n", b"[]\n", b"{}\n", b'{"id":true,"result":{}}\n']
)
def test_invalid_frames_are_rejected(wire):
    with pytest.raises(ProtocolError):
        JsonLines().feed(wire)


def test_incomplete_frame_at_eof_is_not_a_success():
    decoder = JsonLines()
    assert decoder.feed(b'{"id":1') == []
    with pytest.raises(ProtocolError):
        decoder.finish()


def test_frame_limit_applies_to_complete_and_partial_lines():
    for wire in (b"x" * 33, b"x" * 33 + b"\n"):
        with pytest.raises(ProtocolError):
            JsonLines(max_bytes=32).feed(wire)


def test_rpc_separates_stderr_and_refuses_unknown_server_requests():
    code = r"""
import json, sys
request = json.loads(sys.stdin.readline())
print('sensitive diagnostic', file=sys.stderr, flush=True)
print(json.dumps({'method':'future/event','params':{}}), flush=True)
print(json.dumps({'id':99,'method':'future/request','params':{}}), flush=True)
answer = json.loads(sys.stdin.readline())
print(json.dumps({'id':request['id'],'result':{'error_code':answer['error']['code']}}), flush=True)
for line in sys.stdin:
    pass
"""

    async def run():
        async with RpcClient([sys.executable, "-u", "-c", code], timeout=2) as client:
            assert await client.request("initialize", {}) == {"error_code": -32601}
            assert client.notifications[0]["method"] == "future/event"
        assert client.process.returncode is not None

    asyncio.run(run())


def test_rpc_error_is_not_result_and_does_not_leak_error_message():
    code = r"""
import json, sys
r=json.loads(sys.stdin.readline())
print(json.dumps({'id':r['id'],'error':{'code':-32602,'message':'secret-value'}}), flush=True)
"""

    async def run():
        async with RpcClient([sys.executable, "-u", "-c", code], timeout=2) as client:
            with pytest.raises(RpcError) as exc:
                await client.request("thread/resume", {})
            assert exc.value.code == -32602
            assert "secret-value" not in str(exc.value)

    asyncio.run(run())


def test_rpc_eof_and_timeout_fail_and_reap_child():
    for code in ("pass", "import sys; sys.stdin.read()"):

        async def run(code=code):
            async with RpcClient(
                [sys.executable, "-u", "-c", code], timeout=0.2
            ) as client:
                with pytest.raises((ProtocolError, TimeoutError)):
                    await client.request("initialize", {})
            assert client.process.returncode is not None

        asyncio.run(run())


def test_permission_request_is_rejected():
    code = r"""
import json, sys
r=json.loads(sys.stdin.readline())
print(json.dumps({'id':99,'method':'item/commandExecution/requestApproval','params':{}}), flush=True)
answer=json.loads(sys.stdin.readline())
print(json.dumps({'id':r['id'],'result':answer['result']}), flush=True)
"""

    async def run():
        async with RpcClient([sys.executable, "-u", "-c", code], timeout=2) as client:
            assert await client.request("initialize", {}) == {"decision": "decline"}

    asyncio.run(run())
