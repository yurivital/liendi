#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
import argparse
import logging
import sqlite3
import sys

from telegram import BotCommand, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    TypeHandler,
)

from conversation_add import (
    start,
    link,
    title,
    description,
    ConversationAddState,
    cancel,
)
from core import init_db, authorization_callback

import commands

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
    prog="Liendi bot",
    description="Liendi bot is a Telegram bot that helps you manage your links for the next liendi",
)


async def set_commands(application):
    await application.bot.setMyCommands(
        [
            BotCommand("add", "Add a link for the next liendi"),
            BotCommand("cancel", "Cancel link submission"),
            BotCommand(
                "list", "Get last added links from 7 days window. Limited to 25 links"
            ),
            BotCommand(
                "liendi", "Generate a liendi link for all submissions in the last week"
            ),
            BotCommand("search", "Search for links by url. Limited to 25 entries"),
        ]
    )


def get_add_conversations():

    cancel_handler = CommandHandler("cancel", cancel)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", start)],
        states={
            ConversationAddState.LINK.value: [
                cancel_handler,
                MessageHandler(filters.TEXT, link),
            ],
            ConversationAddState.TITLE.value: [
                cancel_handler,
                MessageHandler(filters.TEXT, title),
            ],
            ConversationAddState.DESCRIPTION.value: [
                cancel_handler,
                MessageHandler(filters.TEXT, description),
            ],
        },
        fallbacks=[cancel_handler],
    )
    return conv_handler


def start_bot(db_path):
    """Start the liendi bot, reactions to telegram commands"""

    logger.info("Starting liendi bot")
    # read config from sqlite database
    con = sqlite3.connect(db_path)
    token = con.execute("SELECT value FROM config where key = 'BOT_TOKEN'").fetchone()[
        0
    ]
    if token is None:
        logger.error("BOT_TOKEN configuration not found in database")
        sys.exit(1)
    if len(token) == 0:
        logger.error("BOT_TOKEN configuration is empty")
        sys.exit(1)

    init_db(con)
    application = ApplicationBuilder().token(token).post_init(set_commands).build()

    handler = TypeHandler(Update, authorization_callback)
    application.add_handler(handler, -1)

    application.add_handler(CommandHandler("list", commands.list_link))
    application.add_handler(CommandHandler("liendi", commands.generate_liendi_link))
    application.add_handler(CommandHandler("search", commands.search_by_url))

    application.add_handler(get_add_conversations())

    application.run_polling()
    con.close()


def add_user(db_path, username):
    """Add a user to the whitelist"""
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO whitelist (username) VALUES (?)", (username,))
    con.commit()
    con.close()


def remove_user(db_path, username):
    """Remove a user from the whitelist"""
    con = sqlite3.connect(db_path)
    con.execute("DELETE FROM whitelist WHERE username = ?", (username,))
    con.commit()
    con.close()


def set_token(db_path, token):
    """Set the bot token"""
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('BOT_TOKEN',?)", (token,)
    )
    con.commit()
    con.close()


def apply_schema_from_con(con):
    """Apply the database schema"""
    schema = """
             CREATE TABLE IF NOT EXISTS config
             (
                 key   TEXT PRIMARY KEY,
                 value TEXT
             ) WITHOUT ROWID;

             CREATE TABLE IF NOT EXISTS links
             (
                 id              INTEGER PRIMARY KEY AUTOINCREMENT,
                 url             TEXT    NOT NULL,
                 short           TEXT    NOT NULL,
                 submited_by     TEXT    NOT NULL,
                 submission_date TEXT    NOT NULL,
                 submission_year INTEGER NOT NULL,
                 submission_week INTEGER NOT NULL
             );

             CREATE INDEX IF NOT EXISTS user_index ON links (submited_by);

             CREATE TABLE IF NOT EXISTS whitelist
             (
                 username TEXT PRIMARY KEY
             );
             """
    con.executescript(schema)


def apply_schema(db_path):
    con = sqlite3.connect(db_path)
    apply_schema_from_con(con)
    con.close()


if __name__ == "__main__":
    parser.add_argument("action")  # positional argument
    parser.add_argument("-d", "--db", help="Database path", required=True)
    parser.add_argument("-u", "--user", help="Username", required=False)
    parser.add_argument("-t", "--token", help="Bot token", required=False)

    args = parser.parse_args()
    logger.info("Starting liendi bot with action: %s", args.action)

    database_path = "file://liendi.db"
    if args.db:
        database_path = args.db
    logger.info("Using database path: %s", database_path)

    if len(database_path) == 0:
        logger.error("No database path provided")
        sys.exit(1)

    apply_schema(database_path)

    match args.action:
        case "start":
            start_bot(database_path)
        case "add-user":
            add_user(database_path, args.user.lower())
        case "remove-user":
            remove_user(database_path, args.user.lower())
        case "set-token":
            set_token(database_path, args.token)
        case _:
            logger.error("Unknown action: %s", args.action)
            sys.exit(1)
