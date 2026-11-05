"""Bounded JSON-lines transport for isolated M1 probes, not the product."""

import asyncio
import json


class ProtocolError(Exception):
    pass


class RpcError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(f"RPC_ERROR_{code}")


class JsonLines:
    def __init__(self, max_bytes=1024 * 1024):
        self.buffer = b""
        self.max_bytes = max_bytes

    def feed(self, chunk):
        self.buffer += chunk
        frames = []
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if len(line) > self.max_bytes:
                raise ProtocolError("FRAME_TOO_LARGE")
            if not line.strip():
                continue
            try:
                frame = json.loads(line)
            except (ValueError, UnicodeError):
                raise ProtocolError("INVALID_JSON") from None
            if not isinstance(frame, dict):
                raise ProtocolError("FRAME_MUST_BE_OBJECT")
            if "id" in frame and (
                isinstance(frame["id"], bool) or not isinstance(frame["id"], (int, str))
            ):
                raise ProtocolError("INVALID_ID")
            if "method" in frame:
                if not isinstance(frame["method"], str) or not frame["method"]:
                    raise ProtocolError("INVALID_METHOD")
            elif "id" not in frame or ("result" in frame) == ("error" in frame):
                raise ProtocolError("INVALID_RESPONSE")
            frames.append(frame)
        if len(self.buffer) > self.max_bytes:
            raise ProtocolError("FRAME_TOO_LARGE")
        return frames

    def finish(self):
        if self.buffer.strip():
            raise ProtocolError("TRUNCATED_FRAME")


class RpcClient:
    def __init__(self, argv, *, timeout=15, env=None, cwd=None):
        self.argv, self.timeout, self.env, self.cwd = argv, timeout, env, cwd
        self.pending, self.notifications = {}, []
        self.sequence, self.failure = 0, None

    async def __aenter__(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
            cwd=self.cwd,
        )
        self.reader = asyncio.create_task(self._read())
        self.stderr_reader = asyncio.create_task(self._discard_stderr())
        return self

    async def _discard_stderr(self):
        while await self.process.stderr.read(65536):
            pass

    async def _send(self, frame):
        self.process.stdin.write((json.dumps(frame) + "\n").encode())
        await self.process.stdin.drain()

    async def notify(self, method, params=None):
        await self._send({"method": method, "params": params or {}})

    async def request(self, method, params):
        if self.failure:
            raise self.failure
        self.sequence += 1
        request_id = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            await self._send({"id": request_id, "method": method, "params": params})
            return await asyncio.wait_for(future, self.timeout)
        finally:
            self.pending.pop(request_id, None)

    async def _read(self):
        decoder = JsonLines()
        try:
            while chunk := await self.process.stdout.read(65536):
                for frame in decoder.feed(chunk):
                    if "method" in frame:
                        if "id" in frame:
                            if frame["method"] in (
                                "item/commandExecution/requestApproval",
                                "item/fileChange/requestApproval",
                            ):
                                await self._send(
                                    {
                                        "id": frame["id"],
                                        "result": {"decision": "decline"},
                                    }
                                )
                            else:
                                await self._send(
                                    {
                                        "id": frame["id"],
                                        "error": {
                                            "code": -32601,
                                            "message": "Unsupported probe request",
                                        },
                                    }
                                )
                        else:
                            self.notifications.append(frame)
                            del self.notifications[:-256]
                    else:
                        future = self.pending.get(frame["id"])
                        if future is not None and not future.done():
                            if "error" in frame:
                                error = frame["error"]
                                code = (
                                    error.get("code", -32603)
                                    if isinstance(error, dict)
                                    else -32603
                                )
                                future.set_exception(RpcError(code))
                            else:
                                future.set_result(frame["result"])
            decoder.finish()
            raise ProtocolError("SERVER_EOF")
        except Exception as exc:
            self.failure = (
                exc
                if isinstance(exc, (ProtocolError, RpcError))
                else ProtocolError("TRANSPORT_CLOSED")
            )
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(self.failure)

    async def __aexit__(self, *_):
        self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 2)
        except TimeoutError:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        finally:
            for task in (self.reader, self.stderr_reader):
                task.cancel()
            await asyncio.gather(
                self.reader, self.stderr_reader, return_exceptions=True
            )
