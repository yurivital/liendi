import datetime
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import commands
import  main


@pytest.fixture
def db_connection():
    connection = sqlite3.connect(":memory:")
    commands.init_db(connection)
    main.apply_schema_from_con(connection)
    yield connection
    commands.db_connection = None

@pytest.fixture
def whitelisted_db(db_connection):
    db_connection.execute("INSERT INTO whitelist (username) VALUES (?);", ("alice",))
    db_connection.commit()
    return db_connection

@pytest.fixture
def populate_db(db_connection):
    db_connection.execute("INSERT INTO links (url, short,submited_by, submission_date, submission_year, submission_week) VALUES (?,?,?,?,?,?);",
                          ("https://example.com/blog/numa", "Example link", "alice", datetime.datetime(2026, 7, 14, 10, 30), 2026, 29))

    db_connection.execute("INSERT INTO links (url, short,submited_by, submission_date, submission_year, submission_week) VALUES (?,?,?,?,?,?);",
                          ("https://example.com/blog/java", "", "bob", datetime.datetime(2026, 7, 14, 12, 45), 2026, 29))

    db_connection.commit()
    return db_connection

def make_update(
    *,
    username="alice",
    chat_id=123,
    text="/add https://example.com Example link",
    entities=None,
    date=None,
    url="https://example.com"
):
    if entities is None:
        entities = [
            SimpleNamespace(
                type="url",
                offset=text.index(url),
                length=len(url),
            )
        ]

    return SimpleNamespace(
        message=SimpleNamespace(
            from_user=SimpleNamespace(username=username),
            text=text,
            entities=entities,
            date=date or datetime.datetime(2026, 7, 14, 10, 30),
        ),
        effective_chat=SimpleNamespace(id=chat_id),
    )


def make_context():
    return SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(),
        )
    )


def test_init_db_sets_global_connection(db_connection):
    assert commands.db_connection is db_connection


def test_is_whitelisted_returns_true_for_whitelisted_user(whitelisted_db):
    assert commands.is_whitelisted("Alice") is True


def test_is_whitelisted_returns_false_for_unknown_user(db_connection):
    assert commands.is_whitelisted("bob") is False


@pytest.mark.asyncio
async def test_add_link_rejects_non_whitelisted_user(db_connection):
    update = make_update(username="bob")
    context = make_context()

    await commands.add_link(update, context)

    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="You are not whitelisted to use this bot",
    )

    rows = db_connection.execute("SELECT * FROM links;").fetchall()
    assert rows == []


@pytest.mark.asyncio
async def test_add_link_requires_url_entity(whitelisted_db):
    update = make_update(text="/add no url here", entities=[])
    context = make_context()

    await commands.add_link(update, context)

    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="The command should have a link after /add",
    )

    rows = whitelisted_db.execute("SELECT * FROM links;").fetchall()
    assert rows == []


@pytest.mark.asyncio
async def test_add_link_inserts_link_for_whitelisted_user(whitelisted_db):
    date = datetime.datetime(2026, 7, 14, 10, 30)
    update = make_update(
        text="/add https://example.com Example link",
        date=date,
    )
    context = make_context()

    await commands.add_link(update, context)

    row = whitelisted_db.execute(
        """
        SELECT url, short, submited_by, submission_date, submission_year, submission_week
        FROM links;
        """
    ).fetchone()

    assert row == (
        "https://example.com",
        "Example link",
        "alice",
        "2026-07-14 10:30:00",
        2026,
        date.isocalendar()[1],
    )

    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="👍 Link added.",
    )


@pytest.mark.asyncio
async def test_list_link_rejects_non_whitelisted_user(db_connection):
    update = make_update(username="bob")
    context = make_context()

    await commands.list_link(update, context)

    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="You are not whitelisted to use this bot",
    )


@pytest.mark.asyncio
async def test_list_link_sends_recent_links_for_user(whitelisted_db):
    whitelisted_db.execute(
        """
        INSERT INTO links (
            url, short, submited_by, submission_date, submission_year, submission_week
        )
        VALUES (?, ?, ?, DATE('now'), ?, ?);
        """,
        ("https://example.com", "Example link", "alice", 2026, 29),
    )
    whitelisted_db.execute(
        """
        INSERT INTO links (
            url, short, submited_by, submission_date, submission_year, submission_week
        )
        VALUES (?, ?, ?, DATE('now'), ?, ?);
        """,
        ("https://other.example", "Other user link", "bob", 2026, 29),
    )
    whitelisted_db.commit()

    update = make_update()
    context = make_context()

    await commands.list_link(update, context)

    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="https://example.com: Example link\n\n",
    )

@pytest.mark.asyncio
async def test_generate_liendi_link_sends_no_links_message(db_connection):
    update = make_update()
    context = make_context()

    await commands.generate_liendi_link(update, context)

    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text="No links found for the last week",
    )


@pytest.mark.asyncio
async def test_generate_liendi_link_groups_links_by_user(db_connection):
    last_week = datetime.datetime.now() - datetime.timedelta(weeks=1)
    year = last_week.year
    week = last_week.isocalendar()[1]

    db_connection.executemany(
        """
        INSERT INTO links (
            url, short, submited_by, submission_date, submission_year, submission_week
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        [
            ("https://alice.example/1", "Alice first", "alice", last_week, year, week),
            ("https://alice.example/2", "Alice second", "alice", last_week, year, week),
            ("https://bob.example/1", "Bob first", "bob", last_week, year, week),
        ],
    )
    db_connection.commit()

    update = make_update()
    context = make_context()

    await commands.generate_liendi_link(update, context)

    assert context.bot.send_message.await_count == 2
    context.bot.send_message.assert_any_await(
        chat_id=123,
        text=(
            "☕ Le liendi de @alice\n\n"
            "Alice first\n"
            "https://alice.example/1\n\n"
            "Alice second\n"
            "https://alice.example/2\n\n"
        ),
    )
    context.bot.send_message.assert_any_await(
        chat_id=123,
        text=(
            "☕ Le liendi de @bob\n\n"
            "Bob first\n"
            "https://bob.example/1\n\n"
        ),
    )

@pytest.mark.asyncio
async def test_search_by_url(populate_db):
    context = make_context()
    text="/search https://example.com/blog/numa"
    await commands.search_by_url(make_update( text=text), context)

    assert context.bot.send_message.await_count == 1
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text=(
            "== Results ==\n"
            "Example link\n"
            "https://example.com/blog/numa\n\n"
            "https://example.com/blog/java\n\n"
        ),
    )
@pytest.mark.asyncio
async def test_search_by_url_partial(populate_db):
    context = make_context()
    text="/search https://example.com"
    await commands.search_by_url(make_update( text=text), context)

    assert context.bot.send_message.await_count == 1
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text=(
            "== Results ==\n"
            "Example link\n"
            "https://example.com/blog/numa\n\n"
            "https://example.com/blog/java\n\n"
        ),
    )

@pytest.mark.asyncio
async def test_search_by_url_not_found(populate_db):
    context = make_context()
    search_url = "https://not-found.com/blog/numa"
    text=f"/search {search_url}"
    await commands.search_by_url(make_update( text=text, url=search_url ), context)

    assert context.bot.send_message.await_count == 1
    context.bot.send_message.assert_awaited_once_with(
        chat_id=123,
        text=(
            "No links found for the given URL"
        ),
    )
