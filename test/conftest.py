from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from telegram import Message
from telegram import Update
from telegram import User
from telegram.ext import ContextTypes


@pytest.fixture
def mock_update():
  update = MagicMock(spec=Update)
  message = MagicMock(spec=Message)
  user = MagicMock(spec=User)
  update.message = message
  update.effective_user = user
  user.id = 4815162342
  message.reply_text = AsyncMock()
  message.reply_to_message = None
  return update


@pytest.fixture
def mock_context():
  context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
  context.bot.send_photo = AsyncMock()
  context.bot.send_message = AsyncMock()
  return context


@pytest.fixture
def mock_db():
  with patch("sqlite3.connect") as mock_connect:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    yield mock_cursor
