import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from security.sanitizer import sanitize_input, contains_injection

logger = logging.getLogger("opennexus.bot.middleware")


def create_access_checker(config: Config):
    async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not update.effective_user:
            return False

        config.reload_whitelist()
        user_id = update.effective_user.id

        if user_id not in config.allowed_users:
            logger.warning("Access denied for user %d", user_id)
            if update.message:
                await update.message.reply_text("Access denied.")
            return False
        return True

    return check_access


def create_sanitize_middleware(config: Config):
    async def sanitize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
        if not update.message or not update.message.text:
            return None

        text = update.message.text
        if contains_injection(text):
            logger.warning(
                "Injection attempt from user %s: %s",
                update.effective_user.id if update.effective_user else "?",
                text[:100],
            )
        return sanitize_input(text)

    return sanitize
