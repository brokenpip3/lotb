from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from telegram import Message

from lotb.common.config import Config
from lotb.plugins.memo import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.memo": {
      "generic": "generic_memo",
      "todo": "todo_memo",
      "book": "book_memo",
      "series": "series_memo",
      "film": "film_memo",
    },
  }.get(key, default)
  return config


@pytest.fixture
def memo_plugin(mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  return plugin


@pytest.mark.asyncio
async def test_memo_generic(mock_update, mock_context, memo_plugin, mock_config):
  mock_update.message.text = "/memo I don't even remember my own name"
  with patch(
    "lotb.plugins.memo.Plugin.get_daily_file_path", return_value="generic_memo_2024_06_15.md"
  ) as mock_get_path, patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_get_path.assert_called_once_with("generic_memo")
    mock_append.assert_called_once_with("generic_memo_2024_06_15.md", "I don't even remember my own name", "\n\n- ")
    mock_update.message.reply_text.assert_called_once_with("Message saved to generic.", quote=True)


@pytest.mark.asyncio
async def test_memo_todo(mock_update, mock_context, memo_plugin):
  mock_update.message.text = "/memo to-do I neeed to remember to do what I need to do"
  with patch(
    "lotb.plugins.memo.Plugin.get_daily_file_path", return_value="todo_memo_2024_06_15.md"
  ) as mock_get_path, patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_get_path.assert_called_once_with("todo_memo")
    mock_append.assert_called_once_with(
      "todo_memo_2024_06_15.md", "I neeed to remember to do what I need to do", "\n\n- TODO "
    )
    mock_update.message.reply_text.assert_called_once_with("Message saved to todo.", quote=True)


@pytest.mark.asyncio
async def test_memo_book(mock_update, mock_context, memo_plugin):
  mock_update.message.text = "/memo to-read I need to read this great book: 1984 - Orwell"
  with patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_append.assert_called_once_with("book_memo", "I need to read this great book: 1984 - Orwell", "\n\n- ")
    mock_update.message.reply_text.assert_called_once_with("Message saved to book.", quote=True)


@pytest.mark.asyncio
async def test_memo_series(mock_update, mock_context, memo_plugin):
  mock_update.message.text = "/memo to-watch-series I need another HBO ones"
  with patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_append.assert_called_once_with("series_memo", "I need another HBO ones", "\n\n- ")
    mock_update.message.reply_text.assert_called_once_with("Message saved to series.", quote=True)


@pytest.mark.asyncio
async def test_memo_film(mock_update, mock_context, memo_plugin):
  mock_update.message.text = "/memo to-watch-film Yet another marvel movie"
  with patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_append.assert_called_once_with("film_memo", "Yet another marvel movie", "\n\n- ")
    mock_update.message.reply_text.assert_called_once_with("Message saved to film.", quote=True)


@pytest.mark.asyncio
async def test_memo_no_quoted_message(mock_update, mock_context, memo_plugin):
  mock_update.message.text = "/memo"
  with patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_append.assert_not_called()
    mock_update.message.reply_text.assert_called_once_with("No quoted message found to save.")


@pytest.mark.asyncio
async def test_memo_quoted_message(mock_update, mock_context, memo_plugin):
  mock_update.message.reply_to_message = MagicMock(spec=Message)
  mock_update.message.reply_to_message.text = "to-do This is a quoted todo memo"
  mock_update.message.text = "/memo"
  with patch(
    "lotb.plugins.memo.Plugin.get_daily_file_path", return_value="todo_memo_2024_06_15.md"
  ) as mock_get_path, patch("lotb.plugins.memo.Plugin.append_to_file") as mock_append:
    await memo_plugin.execute(mock_update, mock_context)
    mock_get_path.assert_called_once_with("todo_memo")
    mock_append.assert_called_once_with("todo_memo_2024_06_15.md", "This is a quoted todo memo", "\n\n- TODO ")
    mock_update.message.reply_text.assert_called_once_with("Message saved to todo.", quote=True)
