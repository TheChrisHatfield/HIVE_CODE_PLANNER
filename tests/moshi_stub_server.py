"""Stub stand-in for `python -m moshi.server` used by test_voice_moshi_server.py.

Accepts the same `--host` / `--port` flags, sends the `0x00` handshake on connect, and then
serves until killed. It loads no model and needs no GPU.
"""

import argparse

from websockets.sync.server import serve


def _handler(ws):
    ws.send(bytes([0x00]))
    for _msg in ws:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    server = serve(_handler, args.host, args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
