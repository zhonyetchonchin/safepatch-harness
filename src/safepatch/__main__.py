from __future__ import annotations

import argparse
import os
from pathlib import Path

from safepatch.runtime import create_demo_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="safepatch")
    parser.add_argument("--demo", action="store_true", help="start demo WebUI")
    parser.add_argument(
        "--host",
        default=os.environ.get("SAFEPATCH_HOST", "127.0.0.1"),
        help="bind host",
    )
    parser.add_argument(
        "--port",
        default=int(os.environ.get("SAFEPATCH_PORT") or os.environ.get("PORT") or "8000"),
        type=int,
        help="bind port",
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("SAFEPATCH_DATA_DIR"),
        help="state and vault directory",
    )
    parser.add_argument(
        "--public-demo",
        action="store_true",
        help="enable public demo mode (disables credential UI)",
    )
    args = parser.parse_args()

    if not args.demo:
        parser.error("only --demo mode is implemented")

    import uvicorn

    uvicorn.run(
        create_demo_app(
            data_dir=Path(args.data_dir) if args.data_dir else None,
            public_demo=args.public_demo,
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
