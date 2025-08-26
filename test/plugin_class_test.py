import logging
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
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


@pytest.mark.asyncio
async def test_plugin_base_send_typing_action(mock_plugin, mock_update, mock_context):
  mock_context.bot.send_chat_action = AsyncMock()
  await mock_plugin.send_typing_action(mock_update, mock_context)
  mock_context.bot.send_chat_action.assert_called_with(chat_id=mock_update.effective_chat.id, action="typing")


@pytest.mark.asyncio
async def test_plugin_base_send_typing_action_no_chat(mock_plugin, mock_context):
  update = MagicMock()
  update.effective_chat = None
  await mock_plugin.send_typing_action(update, mock_context)
  mock_context.bot.send_chat_action.assert_not_called()


def test_plugin_base_set_plugins(mock_plugin):
  plugins = ["plugin1", "plugin2"]
  mock_plugin.set_plugins(plugins)
  assert mock_plugin.plugins == plugins


@pytest.mark.asyncio
async def test_plugin_base_intercept_patterns_matched(mock_plugin, mock_update, mock_context):
  action_called = False

  async def mock_action(update, context):
    nonlocal action_called
    action_called = True

  pattern_actions = {"test.*pattern": mock_action}
  mock_update.message.text = "this is a test pattern match"

  result = await mock_plugin.intercept_patterns(mock_update, mock_context, pattern_actions)
  assert result is True
  assert action_called is True


@pytest.mark.asyncio
async def test_plugin_base_intercept_patterns_not_matched(mock_plugin, mock_update, mock_context):
  action_called = False

  async def mock_action(update, context):
    nonlocal action_called
    action_called = True

  pattern_actions = {"nonexistent.*pattern": mock_action}
  mock_update.message.text = "this won't match anything"

  result = await mock_plugin.intercept_patterns(mock_update, mock_context, pattern_actions)
  assert result is False
  assert action_called is False


@pytest.mark.asyncio
async def test_plugin_base_intercept_patterns_no_message(mock_plugin, mock_context):
  update = MagicMock()
  update.message = None

  result = await mock_plugin.intercept_patterns(update, mock_context, {})
  assert result is False


@pytest.mark.asyncio
async def test_plugin_base_intercept_patterns_no_text(mock_plugin, mock_update, mock_context):
  mock_update.message.text = None

  result = await mock_plugin.intercept_patterns(mock_update, mock_context, {})
  assert result is False


def test_plugin_base_set_job_queue(mock_plugin):
  job_queue = MagicMock()
  mock_plugin.set_job_queue(job_queue)


@patch("logging.getLogger")
def test_plugin_base_wrap_llm_logging(mock_get_logger, mock_plugin):
  mock_logger = MagicMock()
  mock_logger.level = logging.INFO
  mock_get_logger.return_value = mock_logger

  with mock_plugin._wrap_llm_logging("test-model"):
    mock_logger.setLevel.assert_called_with(logging.WARNING)

  mock_logger.setLevel.assert_called_with(logging.INFO)


@pytest.mark.asyncio
@patch("litellm.acompletion")
async def test_plugin_base_llm_completion_error(mock_acompletion, mock_plugin):
  mock_acompletion.side_effect = httpx.HTTPError("HTTP error")

  with pytest.raises(httpx.HTTPError):
    await mock_plugin.llm_completion([{"role": "user", "content": "test"}], "test-model")


@pytest.mark.asyncio
@patch("litellm.acompletion")
async def test_plugin_base_llm_completion_default_model(mock_acompletion, mock_plugin, caplog):
  mock_acompletion.return_value = MagicMock()

  with caplog.at_level(logging.WARNING):
    await mock_plugin.llm_completion([{"role": "user", "content": "test"}])

  assert any("no model specified" in msg for msg in caplog.messages)
  mock_acompletion.assert_called()


@pytest.mark.asyncio
async def test_plugin_base_execute_not_implemented(mock_update, mock_context):
  plugin = PluginBase("test", "test plugin")
  with pytest.raises(NotImplementedError):
    await plugin.execute(mock_update, mock_context)
