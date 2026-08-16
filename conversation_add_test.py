# SPDX-License-Identifier: LGPL-2.1-or-later

import sqlite3
from unittest.mock import Mock

import pytest
from telegram.ext import ConversationHandler

import conversation_add
import core
import main
from commands_tests import make_context, make_update


@pytest.mark.asyncio
async def test_workflow():
    context = make_context()

    update = make_update(text="/start", url="")
    next_step = await conversation_add.start(update, context)
    assert next_step == conversation_add.ConversationAddState.LINK.value
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="👋 Hi! Send me the link you’d like to add.\nType /cancel to cancel at any time.",
    )

    # The user sent not a link, stay at LINK state
    update = make_update(text="Not a link", url="")
    context.bot.send_message.reset_mock()
    next_step = await conversation_add.link(update, context)
    assert next_step == conversation_add.ConversationAddState.LINK.value
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123, text="😵 I couldn’t find a valid link. Please send a URL."
    )

    # The user sent a link
    url = "https://example.com"
    update = make_update(text=url, url=url)
    context.bot.send_message.reset_mock()
    next_step = await conversation_add.link(update, context)
    assert next_step == conversation_add.ConversationAddState.TITLE.value
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123, text="👉 Great! Now give this link a title."
    )

    # The user sent a title
    update = make_update(text="This is a title", url="")
    context.bot.send_message.reset_mock()
    next_step = await conversation_add.title(update, context)
    assert next_step == conversation_add.ConversationAddState.DESCRIPTION.value
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123, text="👉 Thanks! Add a short description of the content."
    )

    # The user described the content, but the database is not working
    mock_connection = Mock(spec=sqlite3.Connection)
    mock_connection.execute.side_effect = sqlite3.DatabaseError("execute failed")
    core.init_db(mock_connection)
    update = make_update(text="This is a short description", url="")
    context.bot.send_message.reset_mock()
    next_step = await conversation_add.description(update, context)
    assert next_step == ConversationHandler.END
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123, text="🥴 Sorry, I couldn’t add the link. Please try again later."
    )

    # The user described the content for a working database
    connection = sqlite3.connect(":memory:")
    core.init_db(connection)
    main.apply_schema_from_con(connection)

    update = make_update(text="This is a short description", url="")
    context.bot.send_message.reset_mock()
    next_step = await conversation_add.description(update, context)
    assert next_step == ConversationHandler.END
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123, text="👍 Link added successfully!"
    )
    # verify database
    row = connection.execute(
        """
        SELECT url, short, submited_by, submission_date, submission_year, submission_week
        FROM links;
        """
    ).fetchone()

    assert row == (
        "https://example.com",
        "This is a title\nThis is a short description",
        "alice",
        update.message.date.isoformat(),
        2026,
        update.message.date.isocalendar()[1],
    )


@pytest.mark.asyncio
async def test_cancel():
    context = make_context()
    update = make_update(text="cancel", url="")
    next_step = await conversation_add.cancel(update, context)
    assert next_step == ConversationHandler.END
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123, text="🤌 Link submission cancelled."
    )
