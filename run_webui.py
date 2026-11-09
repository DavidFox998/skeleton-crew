#!/usr/bin/env python3
"""Start the Executor web skin.

Usage:
    python run_webui.py [--port N]

Defaults to port 8000 if --port is not supplied and the PORT environment
variable is not set.
"""

import argparse
import os
import pathlib

from webui.state import HouseRegister
from webui.server import EstateHandler, run

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def main() -> None:
    parser = argparse.ArgumentParser(description="Start The Estate Desk web server.")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8000)),
        help="TCP port to listen on (default: 8000 or $PORT)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    register = HouseRegister(
        will_paths=[
            str(FIXTURES / "will_2019.json"),
            str(FIXTURES / "will_2024.json"),
        ],
        death_record_paths=[
            str(FIXTURES / "death_record.json"),
        ],
    )
    EstateHandler.register = register
    run(host=args.host, port=args.port, register=register)


if __name__ == "__main__":
    main()
