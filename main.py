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
    parser.add_argument("mode", nargs="?", default="bot", choices=["bot", "web"], help="Mode to run (bot or web)")
    args = parser.parse_args()

    logger.info("OpenNexus starting in %s mode...", args.mode.upper())

    config = Config()

    errors = config.validate()
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

    if args.mode == "bot":
        logger.info("Initializing Telegram bot...")
        app = setup_bot(config)

        logger.info(
            "OpenNexus is live. Default provider: %s. Polling started.",
            config.default_provider,
        )
        app.run_polling(drop_pending_updates=True)
    elif args.mode == "web":
        import uvicorn
        from web.webui import create_app
        app = create_app(config)
        logger.info("Starting Web UI on http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
