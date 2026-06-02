# SPDX-License-Identifier: LGPL-2.1-or-later
import datetime
import itertools
import logging

import telegram
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

db_connection = None


def init_db(con):
    global db_connection
    db_connection = con


def is_whitelisted(username):
    """Check if a user is whitelisted to use the bot"""
    whitelist_stmt = "SELECT COUNT(*) FROM whitelist WHERE username = ?;"
    count = db_connection.execute(whitelist_stmt, (username.lower(),))
    return count.fetchone()[0] == 1


async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /add command to add a link to the database"""
    logger.info("Received add link command")
    logger.debug(f"Update details: {update}")
    # find the link in the message

    if not is_whitelisted(update.message.from_user.username):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You are not whitelisted to use this bot",
        )
        return

    link = next(
        (e for e in update.message.entities if e.type == telegram.MessageEntity.URL),
        None,
    )

    if link is None:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="The command should have a link after /add",
        )
        return

    link = update.message.text[link.offset : link.offset + link.length]
    short = update.message.text.replace("/add ", "").replace(link, "").strip()
    user = update.message.from_user.username
    date = update.message.date
    year = date.year
    week = date.isocalendar()[1]

    stmt = "INSERT INTO links (url ,short,submited_by, submission_date ,submission_year,submission_week) VALUES (?,?,?,?,?,?);"
    try:
        db_connection.execute(stmt, (link, short, user, date, year, week))
        db_connection.commit()
    except Exception as e:
        logger.error(f"Error adding link: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=f"Error adding link"
        )
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=f"👍 Link added."
    )


async def list_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /list command to get a link from the database"""
    logger.info("Received list link command")
    logger.debug(f"Update details: {update}")
    if not is_whitelisted(update.message.from_user.username):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You are not whitelisted to use this bot",
        )
        return

    stmt = "SELECT  url, short FROM links WHERE submited_by = ? AND submission_date >= DATE('now', '-7 days') ORDER BY DATE(submission_date) DESC LIMIT 25;"
    try:
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
