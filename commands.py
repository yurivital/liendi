# SPDX-License-Identifier: LGPL-2.1-or-later
import datetime
import itertools
import logging

from telegram import Update
from telegram.ext import ContextTypes

from core import extract_link, get_connection

logger = logging.getLogger(__name__)


async def list_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /list command to get a link from the database"""
    logger.info("Received list link command")
    logger.debug(f"Update details: {update}")
    stmt = "SELECT  url, short FROM links WHERE submited_by = ? AND submission_date >= DATE('now', '-7 days') ORDER BY DATE(submission_date) DESC LIMIT 25;"
    try:
        db_connection = get_connection()
        cursor = db_connection.execute(stmt, (update.message.from_user.username,))
        links = cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching links: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Error fetching links"
        )
        return
    text = ""
    for link in links:
        text += f"{link[0]}: {link[1]}\n\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def generate_liendi_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a liendi link for all submissions in the last 7 days"""

    last_week_date = datetime.datetime.now() - datetime.timedelta(weeks=1)
    week = last_week_date.isocalendar()[1]
    year = last_week_date.year
    weekly_liendi_stmt = "SELECT submited_by, url, short FROM links WHERE submission_year = ? AND submission_week = ? ORDER BY submited_by;"
    db_connection = get_connection()
    cursor = db_connection.execute(
        weekly_liendi_stmt,
        (
            year,
            week,
        ),
    )
    links = cursor.fetchall()

    # Send a message per user with all their links
    if len(links) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="No links found for the last week"
        )
        return
    links_per_user = itertools.groupby(links, key=lambda x: x[0])

    for user, user_links in links_per_user:
        user_text = f"☕ Le liendi de @{user}\n\n"
        for link in user_links:
            user_text += f"{link[2]}\n{link[1]}\n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=user_text)


async def search_by_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for links by URL"""
    logger.info("Received list search command")
    link = extract_link(update.message)

    if link is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="The command should have a link after /search",
        )
        return None

    search_stmt = "SELECT url, short FROM links WHERE url LIKE ? LIMIT 25;"
    db_connection = get_connection()
    cursor = db_connection.execute(search_stmt, (f"%{link}%",))

    links = cursor.fetchall()
    if len(links) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="No links found for the given URL",
        )
        return None

    user_text = "== Results ==\n"
    for db_link in links:
        if len(db_link[1]) == 0:
            user_text += f"{db_link[0]}\n\n"
        else:
            user_text += f"{db_link[1]}\n{db_link[0]}\n\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=user_text)
    return None
