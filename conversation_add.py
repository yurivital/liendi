# SPDX-License-Identifier: LGPL-2.1-or-later

import logging
from enum import Enum

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from core import extract_link, get_connection

logger = logging.getLogger(__name__)


class ConversationAddState(Enum):
    """States of conversation for adding a link"""

    LINK = 0
    TITLE = 1
    DESCRIPTION = 2
    EDIT = 3


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user the link to add."""
    context.user_data.clear()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 Hi! Send me the link you’d like to add.\nType /cancel to cancel at any time.",
    )
    return ConversationAddState.LINK.value


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Extract the link to add."""
    link = extract_link(update.message)
    logger.debug("Link extracted: %s", link)
    if link is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="😵 I couldn’t find a valid link. Please send a URL.",
        )
        return ConversationAddState.LINK.value

    context.user_data["link"] = link
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👉 Great! Now give this link a title.",
    )
    return ConversationAddState.TITLE.value


async def title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Extract the title to add."""
    title = update.message.text
    context.user_data["title"] = title
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👉 Thanks! Add a short description of the content.",
    )
    return ConversationAddState.DESCRIPTION.value


async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Read the description and persist the link."""
    link = context.user_data["link"]
    url_description = update.message.text
    short = f"{context.user_data['title']}\n{url_description}"
    user = update.message.from_user.username
    date = update.message.date
    year = date.year
    week = date.isocalendar()[1]

    stmt = "INSERT INTO links (url ,short,submited_by, submission_date ,submission_year,submission_week) VALUES (?,?,?,?,?,?);"
    try:
        db_connection = get_connection()
        db_connection.execute(stmt, (link, short, user, date.isoformat(), year, week))
        db_connection.commit()
    except Exception as e:
        logger.error(f"Error adding link: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🥴 Sorry, I couldn’t add the link. Please try again later.",
        )
        return ConversationHandler.END
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="👍 Link added successfully!"
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    logger.info("Link submission cancelled.")
    context.user_data.clear()
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="🤌 Link submission cancelled."
    )
    return ConversationHandler.END
