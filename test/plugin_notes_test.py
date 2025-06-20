from unittest.mock import MagicMock

import pytest

from lotb.common.config import Config
from lotb.plugins.notes import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database_name": ":memory:",
    "plugins.notes": {"debug": True},
  }.get(key, default)
  return config


@pytest.mark.asyncio
async def test_add_note_success(mock_update, mock_context, mock_db, mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.db_cursor = mock_db
  plugin.initialize()
  mock_update.message.text = "/notes add the north remembers"
  await plugin.execute(mock_update, mock_context)
  assert mock_db.execute.call_count == 2
  mock_db.execute.assert_any_call(
    "INSERT INTO notes (user_id, note) VALUES (?, ?)", (4815162342, "the north remembers")
  )
  mock_update.message.reply_text.assert_called_once_with("Note added successfully.", do_quote=True)


@pytest.mark.asyncio
async def test_view_notes_with_notes(mock_update, mock_context, mock_db, mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.db_cursor = mock_db
  plugin.initialize()
  mock_update.message.text = "/notes list"
  mock_db.fetchall.return_value = [(1, "Note 1"), (2, "Note 2")]
  await plugin.execute(mock_update, mock_context)
  assert mock_db.execute.call_count == 2
  mock_db.execute.assert_any_call("SELECT id, note FROM notes WHERE user_id = ?", (4815162342,))
  mock_update.message.reply_text.assert_called_once_with("Your notes:\n1: Note 1\n2: Note 2", do_quote=True)


@pytest.mark.asyncio
async def test_view_notes_no_notes(mock_update, mock_context, mock_db, mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  mock_update.message.text = "/notes list"
  mock_db.fetchall.return_value = []
  await plugin.execute(mock_update, mock_context)
  assert mock_db.execute.call_count == 2
  mock_db.execute.assert_any_call("SELECT id, note FROM notes WHERE user_id = ?", (4815162342,))
  mock_update.message.reply_text.assert_called_once_with("You have no notes.", do_quote=True)


@pytest.mark.asyncio
async def test_delete_note_success(mock_update, mock_context, mock_db, mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.db_cursor = mock_db
  plugin.initialize()
  mock_update.message.text = "/notes delete 1"
  mock_db.rowcount = 1
  await plugin.execute(mock_update, mock_context)
  assert mock_db.execute.call_count == 2
  mock_db.execute.assert_any_call("DELETE FROM notes WHERE id = ? AND user_id = ?", (1, 4815162342))
  mock_update.message.reply_text.assert_called_once_with("Note deleted successfully.", do_quote=True)


@pytest.mark.asyncio
async def test_delete_note_not_found(mock_update, mock_context, mock_db, mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.db_cursor = mock_db
  plugin.initialize()
  mock_update.message.text = "/notes delete 1"
  mock_db.rowcount = 0
  await plugin.execute(mock_update, mock_context)
  assert mock_db.execute.call_count == 2
  mock_db.execute.assert_any_call("DELETE FROM notes WHERE id = ? AND user_id = ?", (1, 4815162342))
  mock_update.message.reply_text.assert_called_once_with(
    "Note not found or you don't have permission to delete it.", do_quote=True
  )


@pytest.mark.asyncio
async def test_invalid_subcommand(mock_update, mock_context, mock_db, mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.db_cursor = mock_db
  plugin.initialize()
  mock_update.message.text = "/notes invalid"
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with(
    "Invalid notes subcommand or missing arguments.", do_quote=True
  )
