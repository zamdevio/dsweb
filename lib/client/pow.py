"""DeepSeekHashV1 PoW solver (bundled wasm)."""
from __future__ import annotations

import base64
import json
import struct

from . import config as cfg
from .errors import UpstreamError


class PoWSolver:
    _cached = None

    def _exports(self):
        if PoWSolver._cached is None:
            import wasmtime

            engine = wasmtime.Engine()
            module = wasmtime.Module(engine, open(cfg.WASM, "rb").read())
            store = wasmtime.Store(engine)
            linker = wasmtime.Linker(engine)
            linker.define_wasi()
            PoWSolver._cached = (store, linker.instantiate(store, module).exports(store))
        return PoWSolver._cached

    def solve(self, challenge: str, salt: str, expire_at: int, difficulty: int) -> int:
        store, ex = self._exports()
        mem = ex["memory"]

        def write(text: str):
            data = text.encode()
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
                raise UpstreamError("pow: no solution found")
            return int(struct.unpack("<d", bytes(view[retptr + 8 : retptr + 16]))[0])
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
            "algorithm": challenge["algorithm"],
            "challenge": challenge["challenge"],
            "salt": challenge["salt"],
            "answer": answer,
            "signature": challenge["signature"],
            "target_path": challenge.get("target_path", target),
        }
        return base64.b64encode(json.dumps(proof).encode()).decode()
