import logging
import sys

from .config import Config
from .sync_logic import SyncEngine


def setup_logging():
    logging.basicConfig(
        level=Config.LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main():
    setup_logging()
    engine = SyncEngine()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "initial":
        engine.initial_sync()
    elif cmd == "run":
        engine.run_polling_loop()
    else:
        print("Usage: python -m src.main [initial|run]")


if __name__ == "__main__":
    main()
