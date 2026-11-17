"""DeepSeekHashV1 PoW solver (bundled wasm).

Engine+Module are cached; each solve gets a fresh Store under a lock so
parallel proxy requests cannot corrupt wasm memory (unreachable trap).

`prove()` retries with caller-supplied fresh challenges — see DeepSeekClient.
"""
from __future__ import annotations

import base64
import json
import struct
import threading

from . import config as cfg
from .errors import UpstreamError

_lock = threading.Lock()
_engine = None
_module = None


class PoWError(UpstreamError):
    """Solver failed for this challenge (retryable with a new one)."""


def _load():
    global _engine, _module
    if _module is not None:
        return _engine, _module
    import wasmtime

    _engine = wasmtime.Engine()
    with open(cfg.WASM, "rb") as fh:
        _module = wasmtime.Module(_engine, fh.read())
    return _engine, _module


def _reset_cache() -> None:
    global _engine, _module
    _engine = None
    _module = None


class PoWSolver:
    def solve(self, challenge: str, salt: str, expire_at: int, difficulty: int) -> int:
        """Solve one challenge. Thread-safe; retries wasm traps once."""
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                return self._solve_once(challenge, salt, expire_at, difficulty)
            except PoWError:
                raise
            except Exception as exc:
                last_err = exc
                with _lock:
                    _reset_cache()
        raise PoWError(f"pow: wasm failed: {last_err}") from last_err

    def _solve_once(
        self, challenge: str, salt: str, expire_at: int, difficulty: int
    ) -> int:
        import wasmtime

        challenge = str(challenge)
        salt = str(salt)
        expire_at = int(expire_at)
        difficulty = int(difficulty)

        with _lock:
            engine, module = _load()
            store = wasmtime.Store(engine)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            ex = linker.instantiate(store, module).exports(store)
            mem = ex["memory"]

            def write(text: str):
                data = text.encode("utf-8")
                ptr = ex["__wbindgen_export_0"](store, len(data), 1)
                view = mem.data_ptr(store)
                for i, b in enumerate(data):
                    view[ptr + i] = b
                return ptr, len(data)

            prefix = f"{salt}_{expire_at}_"
            retptr = ex["__wbindgen_add_to_stack_pointer"](store, -16)
            try:
                cp, cl = write(challenge)
                pp, pl = write(prefix)
                ex["wasm_solve"](store, retptr, cp, cl, pp, pl, float(difficulty))
                view = mem.data_ptr(store)
                status = struct.unpack("<i", bytes(view[retptr : retptr + 4]))[0]
                if status == 0:
                    # Miss on this challenge — caller fetches a fresh one.
                    raise PoWError("pow: no solution found")
                answer = int(struct.unpack("<d", bytes(view[retptr + 8 : retptr + 16]))[0])
                if answer < 0:
                    raise PoWError("pow: invalid answer")
                return answer
            finally:
                ex["__wbindgen_add_to_stack_pointer"](store, 16)

    def prove(self, challenge: dict, target: str) -> str:
        answer = self.solve(
            challenge=challenge["challenge"],
            salt=challenge["salt"],
            expire_at=challenge["expire_at"],
            difficulty=challenge["difficulty"],
        )
        proof = {
            "algorithm": challenge.get("algorithm") or "DeepSeekHashV1",
            "challenge": challenge["challenge"],
            "salt": challenge["salt"],
            "answer": answer,
            "signature": challenge["signature"],
            "target_path": challenge.get("target_path", target),
        }
        return base64.b64encode(json.dumps(proof, separators=(",", ":")).encode()).decode()
