"""Launch the vocabulary trainer web server on the local network.

Run with:  uv run main.py   (or: uv run python main.py)
Then open the printed URL on your tablet (same Wi-Fi network).
"""

from __future__ import annotations

import socket

import uvicorn


def lan_ip() -> str:
    """Best-effort local network IP address."""

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    host = "0.0.0.0"
    port = 8000
    ip = lan_ip()
    print("=" * 52)
    print("  English Vocabulary Trainer")
    print(f"  Local:    http://127.0.0.1:{port}")
    print(f"  Network:  http://{ip}:{port}   <- open this on your tablet")
    print("=" * 52)
    uvicorn.run("vocab.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
