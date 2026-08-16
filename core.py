# SPDX-License-Identifier: LGPL-2.1-or-later
import logging
from sqlite3 import Connection

from telegram import Update, MessageEntity
from telegram.ext import ContextTypes, ApplicationHandlerStop

db_connection: Connection


logger = logging.getLogger(__name__)


def init_db(con):
    global db_connection
    db_connection = con


def get_connection() -> Connection:
    """Get the database connection"""
    return db_connection


def extract_link(message):
    """Extract the link from a message"""
    link = next(
        (e for e in message.entities if e.type == MessageEntity.URL),
        None,
    )
    if link is None:
        return None
    if link.offset == 0 and link.length == 0:
        return None
    return message.text[link.offset : link.offset + link.length]


def is_whitelisted(username):
    """Check if a user is whitelisted to use the bot"""
    whitelist_stmt = "SELECT COUNT(*) FROM whitelist WHERE username = ?;"
    count = db_connection.execute(whitelist_stmt, (username.lower(),))
    return count.fetchone()[0] == 1


async def authorization_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback to check if the user is authorized to use the bot"""
    if not is_whitelisted(update.effective_user.username):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You are not authorized to use this bot.",
        )
        logger.warning(
            f"Unauthorized user attempted to use the bot : {update.effective_user.username or 'no-username'} ({update.effective_user.id})"
        )
        raise ApplicationHandlerStop
