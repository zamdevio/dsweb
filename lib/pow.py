#!/usr/bin/env python3
"""
pop.py - DeepSeek Web PoW (DeepSeekHashV1) solver.

Reads a challenge JSON on stdin:
  {"algorithm","challenge","salt","difficulty","expire_at","signature","target_path"}

Writes the base64-encoded, JSON proof to stdout (value for the
`x-ds-pow-response` header). Requires the bundled wasm + `wasmtime`.
"""
import sys
import os
import json
import base64
import struct

WASM_PATH = os.environ.get("DS_WASM") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "wasm", "sha3_wasm_bg.wasm"
)


def solve(challenge: dict) -> str:
    import wasmtime

    if challenge.get("algorithm") != "DeepSeekHashV1":
        raise SystemExit("unsupported algorithm: %r" % challenge.get("algorithm"))

    engine = wasmtime.Engine()
    with open(WASM_PATH, "rb") as fh:
        module = wasmtime.Module(engine, fh.read())

    store = wasmtime.Store(engine)
    linker = wasmtime.Linker(engine)
    linker.define_wasi()
    instance = linker.instantiate(store, module)
    exports = instance.exports(store)
    memory = exports["memory"]

    def write(text: str):
        data = text.encode()
        ptr = exports["__wbindgen_export_0"](store, len(data), 1)
        view = memory.data_ptr(store)
        for i, b in enumerate(data):
            view[ptr + i] = b
        return ptr, len(data)

    prefix = "%s_%s_" % (challenge["salt"], challenge["expire_at"])
    retptr = exports["__wbindgen_add_to_stack_pointer"](store, -16)
    try:
        cptr, clen = write(challenge["challenge"])
        pptr, plen = write(prefix)
        exports["wasm_solve"](
            store,
            retptr,
            cptr,
            clen,
            pptr,
            plen,
            float(challenge["difficulty"]),
        )
        view = memory.data_ptr(store)
        status = struct.unpack("<i", bytes(view[retptr : retptr + 4]))[0]
        if status == 0:
            raise SystemExit("no solution found")
        answer = int(struct.unpack("<d", bytes(view[retptr + 8 : retptr + 16]))[0])
    finally:
        exports["__wbindgen_add_to_stack_pointer"](store, 16)

    proof = {
        "algorithm": challenge["algorithm"],
        "challenge": challenge["challenge"],
        "salt": challenge["salt"],
        "answer": answer,
        "signature": challenge["signature"],
        "target_path": challenge["target_path"],
    }
    return base64.b64encode(json.dumps(proof).encode()).decode()


def main() -> None:
    try:
        challenge = json.load(sys.stdin)
    except Exception as exc:  # pragma: no cover
        raise SystemExit("bad challenge json: %s" % exc)
    sys.stdout.write(solve(challenge))


if __name__ == "__main__":
    main()
