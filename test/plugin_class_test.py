import logging
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.plugin_class import SecurityValidator


class MockPlugin(PluginBase):
  def __init__(self):
    super().__init__("mock", "mock class plugin", require_auth=False)

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


@pytest.fixture
def mock_plugin():
  plugin = MockPlugin()
  plugin.config = {"core": {"database": ":memory:"}}
  return plugin


@pytest.fixture
def security_validator():
  return SecurityValidator()


def test_security_validator_validate_user_input_clean(security_validator):
  text = "Hello with no suspicious content"
  is_valid, msg = security_validator.validate_user_input(text)
  assert is_valid
  assert msg == ""


def test_security_validator_validate_user_input_suspicious(security_validator):
  text = "<script>alert('xss')</script>"
  is_valid, msg = security_validator.validate_user_input(text)
  assert not is_valid
  assert "suspicious" in msg


def test_security_validator_llm_validate_tool_name_clean(security_validator):
  is_valid, msg = security_validator.llm_validate_tool_name("get_data")
  assert is_valid
  assert msg == ""


def test_security_validator_llm_validate_tool_name_blocked(security_validator):
  is_valid, msg = security_validator.llm_validate_tool_name("exec_shell")
  assert not is_valid
  assert "blocked" in msg


def test_plugin_base_escape_markdown():
  text = "Hello _world_ *with* [markdown]"
  escaped = PluginBase.escape_markdown(None, text)
  assert escaped == "Hello \\_world\\_ \\*with\\* \\[markdown\\]"


def test_plugin_base_logging(mock_plugin, caplog):
  with caplog.at_level(logging.INFO):
    mock_plugin.log_info("test info")
    mock_plugin.log_warning("test warning")
    mock_plugin.log_error("test error")

  assert any("test info" in msg for msg in caplog.messages)
  assert any("test warning" in msg for msg in caplog.messages)
  assert any("test error" in msg for msg in caplog.messages)


def test_plugin_base_set_config(mock_plugin):
  mock_config = {"core": {"database": "test.db"}}
  mock_plugin.set_config(mock_config)
  assert mock_plugin.config == mock_config


def test_plugin_base_initialize_plugin_enabled(mock_plugin, caplog):
  mock_plugin.config = {"plugins.mock": {"enabled": True}}
  with caplog.at_level(logging.INFO):
    mock_plugin.initialize_plugin()
  assert any("Mock plugin is enabled" in msg for msg in caplog.messages)


def test_plugin_base_initialize_plugin_disabled(mock_plugin):
  mock_plugin.config = {"plugins.mock": {"enabled": False}}
  with pytest.raises(ValueError):
    mock_plugin.initialize_plugin()


@patch("sqlite3.connect")
def test_plugin_base_create_table(mock_connect, mock_plugin):
  mock_plugin.set_config({})
  query = "CREATE TABLE test (id INT)"
  mock_plugin.create_table(query)
  mock_plugin.db_cursor.execute.assert_called_with(query)


@patch("sqlite3.connect")
def test_plugin_base_execute_query(mock_connect, mock_plugin):
  mock_plugin.set_config({})
  query = "INSERT INTO test VALUES (1)"
  mock_plugin.execute_query(query)
  mock_plugin.db_cursor.execute.assert_called_with(query, ())


@pytest.mark.asyncio
async def test_plugin_base_reply_message(mock_plugin):
  update = MagicMock()
  update.message = MagicMock()
  update.message.reply_text = AsyncMock()
  context = MagicMock()
  message = "this is a test message"

  await mock_plugin.reply_message(update, context, message)
  update.message.reply_text.assert_called_with(message)


@pytest.mark.asyncio
async def test_plugin_base_reply_quote_message(mock_plugin):
  update = MagicMock()
  update.message = MagicMock()
  update.message.reply_text = AsyncMock()
  context = MagicMock()
  message = "this is a quoted message"

  await mock_plugin.reply_quote_message(update, context, message)
  update.message.reply_text.assert_called_with(message, do_quote=True)


def test_plugin_base_is_authorized(mock_plugin, mock_update):
  mock_plugin.admin_ids = [mock_update.effective_user.id]
  assert mock_plugin.is_authorized(mock_update)
  mock_plugin.require_auth = True
  mock_plugin.admin_ids = [456]
  assert not mock_plugin.is_authorized(mock_update)


def test_plugin_base_group_is_authorized(mock_plugin, mock_update):
  mock_plugin.auth_group_ids = [996699]
  assert mock_plugin.group_is_authorized(mock_update)
  mock_plugin.auth_group_enabled = True
  mock_plugin.auth_group_ids = [456]
  assert not mock_plugin.group_is_authorized(mock_update)
