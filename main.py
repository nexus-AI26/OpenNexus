import logging
import sys
import argparse
from pathlib import Path

from config import Config, CONFIG_DIR
from security.scanner import scan_directory, check_hardcoded_keys
from bot.handlers import setup_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("opennexus")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenNexus AI Assistant")
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["all", "bot", "web"],
        help="all = Telegram + Web UI (default); bot = Telegram only; web = Web UI only",
    )
    args = parser.parse_args()

    logger.info("OpenNexus starting in %s mode...", args.mode.upper())

    config = Config()

    errors = config.validate(mode=args.mode)
    if errors:
        for err in errors:
            logger.error("CONFIG: %s", err)
        sys.exit(1)

    logger.info("Running startup security scan...")
    secret_warnings = scan_directory(CONFIG_DIR)
    for warning in secret_warnings:
        logger.warning("SECRETS SCAN: %s", warning)

    source_dir = Path(__file__).parent
    code_warnings = check_hardcoded_keys(source_dir)
    for warning in code_warnings:
        logger.warning("HARDCODED KEY: %s", warning)

    if secret_warnings or code_warnings:
        logger.warning(
            "Found %d security warning(s). Review above.",
            len(secret_warnings) + len(code_warnings),
        )

    if args.mode == "web":
        import uvicorn
        from web.webui import create_app

        app = create_app(config)
        logger.info("Web UI at http://0.0.0.0:8000 (Ctrl+C to stop)")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    elif args.mode == "bot":
        if not config.bot_token:
            logger.error("Bot token missing. Use `web` mode or set bot_token in config.")
            sys.exit(1)
        logger.info("Initializing Telegram bot...")
        app = setup_bot(config)
        logger.info(
            "OpenNexus bot live. Default provider: %s. Polling started.",
            config.default_provider,
        )
        app.run_polling(drop_pending_updates=True)
    else:
        import threading
        import uvicorn
        from web.webui import create_app

        if not config.bot_token:
            app = create_app(config)
            logger.warning("No bot_token — Web UI only (same as `web` mode).")
            logger.info("Web UI at http://0.0.0.0:8000")
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
            return

        web_app = create_app(config)

        def _run_web() -> None:
            uvicorn.run(web_app, host="0.0.0.0", port=8000, log_level="warning")

        web_thread = threading.Thread(target=_run_web, name="opennexus-web", daemon=True)
        web_thread.start()
        logger.info("Web UI running in background at http://0.0.0.0:8000")

        logger.info("Initializing Telegram bot...")
        app = setup_bot(config)
        logger.info(
            "OpenNexus is live (Telegram + Web). Default provider: %s.",
            config.default_provider,
        )
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
