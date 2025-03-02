from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from lotb.plugins.quote import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "core.database_name": ":memory:",
    "plugins.quote": {"enabled": True},
  }.get(key, default)
  return config


@pytest.fixture
def plugin(mock_config, mock_db):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.db_cursor = mock_db
  plugin.initialize()
  mock_db.execute.reset_mock()
  return plugin


@pytest.mark.asyncio
async def test_add_quote_success(mock_update, mock_context, mock_db, plugin):
  mock_reply = MagicMock()
  mock_reply.text = "Try to be a rainbow in someone's cloud"
  mock_reply.from_user.full_name = "Maya Angelou"
  mock_update.message.reply_to_message = mock_reply
  mock_update.message.text = "/quote"
  await plugin.execute(mock_update, mock_context)
  mock_db.execute.assert_called_once_with(
    "INSERT INTO quotes (user_id, chat_id, quote) VALUES (?, ?, ?)",
    (4815162342, 996699, "Try to be a rainbow in someone's cloud\n\n- Maya Angelou"),
  )
  mock_update.message.reply_text.assert_awaited_once_with("Quote added successfully", quote=True)


@pytest.mark.asyncio
async def test_add_quote_no_reply(mock_update, mock_context, mock_db, plugin):
  mock_update.message.reply_to_message = None
  mock_update.message.text = "/quote"
  mock_db.fetchall.return_value = []
  await plugin.execute(mock_update, mock_context)
  mock_db.execute.assert_called_once_with("SELECT quote FROM quotes WHERE chat_id = ?", (996699,))
  mock_update.message.reply_text.assert_awaited_once_with("No quotes available", quote=True)


@pytest.mark.asyncio
async def test_get_quote_with_term(mock_update, mock_context, mock_db, plugin):
  mock_update.message.text = "/quote wrong"
  mock_db.fetchall.return_value = [
    ("The answer is inside you but it is wrong\n\n- Guzzanti",),
    ("Quoting is like something else but it's wrong\n\n- Pinguini Tattici Nucleari",),
  ]
  await plugin.execute(mock_update, mock_context)
  mock_db.execute.assert_called_once_with(
    "SELECT quote FROM quotes WHERE quote LIKE ? AND chat_id = ?", ("%wrong%", 996699)
  )
  called_with = mock_update.message.reply_text.call_args[0][0]
  assert called_with in [
    "The answer is inside you but it is wrong\n\n- Guzzanti",
    "Quoting is like something else but it's wrong\n\n- Pinguini Tattici Nucleari",
  ]


@pytest.mark.asyncio
async def test_get_quote_no_match(mock_update, mock_context, mock_db, plugin):
  mock_update.message.text = "/quote shamalaia"
  mock_db.fetchall.return_value = []
  await plugin.execute(mock_update, mock_context)
  mock_db.execute.assert_called_once_with(
    "SELECT quote FROM quotes WHERE quote LIKE ? AND chat_id = ?", ("%shamalaia%", 996699)
  )
  mock_update.message.reply_text.assert_awaited_once_with("No quotes found containing that term", quote=True)


@pytest.mark.asyncio
async def test_with_no_term_only_space_no_quote_available(mock_update, mock_context, mock_db, plugin):
  mock_update.message.text = "/quote  "
  mock_update.message.reply_to_message = None
  mock_db.fetchall.return_value = []
  await plugin.execute(mock_update, mock_context)
  mock_db.execute.assert_called_once_with("SELECT quote FROM quotes WHERE chat_id = ?", (996699,))
  mock_update.message.reply_text.assert_awaited_once_with("No quotes available", quote=True)


@pytest.mark.asyncio
async def test_with_no_term_only_space_return_quote(mock_update, mock_context, mock_db, plugin):
  mock_update.message.text = "/quote  "
  mock_update.message.reply_to_message = None
  mock_db.fetchall.return_value = [
    ("The answer is inside you but it is wrong\n\n- Guzzanti",),
    ("Quoting is like something else but it's wrong\n\n- Pinguini Tattici Nucleari",),
  ]
  await plugin.execute(mock_update, mock_context)
  mock_db.execute.assert_called_once_with("SELECT quote FROM quotes WHERE chat_id = ?", (996699,))
  called_with = mock_update.message.reply_text.call_args[0][0]
  # assert in a list to avoid flaky test
  assert called_with in [
    "The answer is inside you but it is wrong\n\n- Guzzanti",
    "Quoting is like something else but it's wrong\n\n- Pinguini Tattici Nucleari",
  ]


@pytest.mark.asyncio
async def test_add_missing_user(mock_update, mock_context, plugin):
  mock_update.effective_user = None
  await plugin.add_quote(mock_update, mock_context, "Some quote")
  mock_update.message.reply_text.assert_awaited_once_with("User information is missing.", quote=True)


@pytest.mark.asyncio
async def test_add_missing_chat(mock_update, mock_context, plugin):
  mock_update.effective_chat = None
  await plugin.add_quote(mock_update, mock_context, "Some quote")
  mock_update.message.reply_text.assert_awaited_once_with("Chat information is missing.", quote=True)


@pytest.mark.asyncio
async def test_add_missing_message(mock_update, mock_context, plugin):
  mock_update.message = None
  plugin.reply_quote_message = AsyncMock()
  await plugin.add_quote(mock_update, mock_context, "It's lost without a message")
  plugin.reply_quote_message.assert_not_called()


@pytest.mark.asyncio
async def test_get_quote_missing_chat(mock_update, mock_context, plugin):
  mock_update.effective_chat = None
  plugin.reply_quote_message = AsyncMock()
  await plugin.get_quote(mock_update, mock_context, "so true but not sent")
  plugin.reply_quote_message.assert_awaited_once_with(mock_update, mock_context, "Chat information is missing")


@pytest.mark.asyncio
async def test_get_random_quote_missing_db_cursor(mock_update, mock_context, plugin):
  mock_update.effective_chat.id = 996699
  plugin.db_cursor = None
  plugin.reply_quote_message = AsyncMock()
  await plugin.get_random_quote(mock_update, mock_context)
  plugin.reply_quote_message.assert_awaited_once_with(mock_update, mock_context, "Database cursor is not available.")


@pytest.mark.asyncio
async def test_get_random_quote_missing_chat(mock_update, mock_context, plugin):
  mock_update.effective_chat = None
  plugin.reply_quote_message = AsyncMock()
  await plugin.get_random_quote(mock_update, mock_context)
  plugin.reply_quote_message.assert_awaited_once_with(mock_update, mock_context, "Chat information is missing")


@pytest.mark.asyncio
async def test_get_quote_missing_db_cursor(mock_update, mock_context, plugin):
  mock_update.effective_chat.id = 996699
  plugin.db_cursor = None
  plugin.reply_quote_message = AsyncMock()
  await plugin.get_quote(mock_update, mock_context, "was great but the db is not ready")
  plugin.reply_quote_message.assert_awaited_once_with(mock_update, mock_context, "Database cursor is not available.")


@pytest.mark.asyncio
async def test_execute_no_command_text(mock_update, mock_context, plugin):
  mock_update.message.text = None
  plugin.reply_quote_message = AsyncMock()
  await plugin.execute(mock_update, mock_context)
  plugin.reply_quote_message.assert_awaited_once_with(mock_update, mock_context, "No command text found")
