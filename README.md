# Liendi Bot

Liendi is a Telegram bot for managing articles shared on monday.

## Configuration

Liendi uses an SQLite database to store its configuration and state.

### Set up instructions

In three easy steps:
1. Set the token given by the BotFather
```shell
python main.py set-token --db liendi.db --token <token> 
```
2. Add the users to the whitelist
```shell
python main.py add-user --db liendi.db --user <username>
```
Nota : you should use the username of the user as it appears in Telegram (ex: @toto).
4. Start the bot with `python3 main.py start --db liendi.db`

## Development

### Requirements

Development requirements:
- uv

Runtime requirements:
- Python 3.14
- SQLite3
- python-telegram-bot

## Telegram commands

Supported commands:
- Telegram command /add: add a link into the database
- Telegram command /list: list the last 25 links within the last 25 days
- Telegram command /liendi: generate liendi for last week. Gathers all links added during the previous week and send a message per contributing user with the list of links and a summary of the week.

## CLI commands
- `python main.py set-token --db <db> --token <token>`, set the bot token.
- `python main.py add-user --db <db> --user <username>`, add a user to the whitelist.
- `python main.py remove-user --db <db> --user <username>`, remove a user from the whitelist.
- `python main.py start --db <db>`: start the bot

parameters:
`<db>` is the path to the database file
`<token>` is the bot token
`<username>` is the username of the username as it appears in Telegram.

