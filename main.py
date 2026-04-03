import logging
import sys
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
    logger.info("OpenNexus starting...")

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

    logger.info("Initializing Telegram bot...")
    app = setup_bot(config)

    logger.info(
        "OpenNexus is live. Default provider: %s. Polling started.",
        config.default_provider,
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
