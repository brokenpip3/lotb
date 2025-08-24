from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.lotb import disable_plugin
from lotb.lotb import enable_plugin
from lotb.lotb import handle_command
from lotb.lotb import handlers
from lotb.lotb import help_command
from lotb.lotb import list_plugins
from lotb.lotb import load_plugins
from lotb.lotb import plugins


@pytest.fixture
def mock_update(mock_update):
  update = mock_update
  update.message.text = "/test"
  return update


@pytest.fixture
def mock_context():
  context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
  context.bot.send_photo = AsyncMock()
  context.bot.send_message = AsyncMock()
  return context


@pytest.fixture
def mock_spec_side_effect():
  def spec_from_file_location_side_effect(name, location):
    mock_module = MagicMock()
    mock_plugin_instance = MagicMock()
    mock_module.Plugin = MagicMock(return_value=mock_plugin_instance)
    spec = MagicMock()
    spec.loader = MagicMock()
    spec.loader.exec_module = lambda module: setattr(module, "Plugin", mock_module.Plugin)
    return spec

  return spec_from_file_location_side_effect


@pytest.mark.asyncio
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.load_plugins")
async def test_handle_command_authorized(mock_load_plugins, mock_plugins, mock_update, mock_context):
  mock_plugin = MagicMock()
  mock_plugin.is_authorized.return_value = True
  mock_plugin.group_is_authorized.return_value = True
  mock_plugin.execute = AsyncMock()
  mock_plugins["test"] = mock_plugin
  await handle_command(mock_update, mock_context)
  mock_plugin.execute.assert_called_once_with(mock_update, mock_context)
  mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.load_plugins")
async def test_handle_command_unauthorized_group(mock_load_plugins, mock_plugins, mock_update, mock_context):
  mock_plugin = MagicMock()
  mock_plugin.group_is_authorized.return_value = False
  mock_plugins["test"] = mock_plugin
  await handle_command(mock_update, mock_context)
  mock_plugin.execute.assert_not_called()


@pytest.mark.asyncio
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.load_plugins")
async def test_handle_command_unauthorized_user(mock_load_plugins, mock_plugins, mock_update, mock_context):
  mock_plugin = MagicMock()
  mock_plugin.is_authorized.return_value = False
  mock_plugin.group_is_authorized.return_value = True
  mock_plugin.execute = AsyncMock()
  mock_plugins["test"] = mock_plugin
  await handle_command(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("you are not authorized to use this command.")


@pytest.mark.asyncio
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.load_plugins")
async def test_help_command(mock_load_plugins, mock_plugins, mock_update, mock_context):
  mock_plugin = MagicMock()
  mock_plugin.description = "Test command"
  mock_plugins["test"] = mock_plugin
  await help_command(mock_update, mock_context)
  expected_text = "Available commands:\n\n/test - Test command\n\nFind more at https://github.com/brokenpip3/lotb"
  mock_update.message.reply_text.assert_called_once_with(expected_text, disable_web_page_preview=True)


@pytest.mark.asyncio
@patch("lotb.lotb.importlib.import_module")
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.application", new_callable=MagicMock)
@patch("lotb.lotb.handlers", new_callable=dict)
async def test_enable_plugin(
  mock_handlers, mock_application, mock_plugins, mock_import_module, mock_update, mock_context
):
  mock_context.args = ["test"]
  mock_module = MagicMock()
  mock_import_module.return_value = mock_module
  mock_plugin_instance = MagicMock()
  mock_module.Plugin.return_value = mock_plugin_instance
  config = MagicMock()
  await enable_plugin(mock_update, mock_context, config)
  mock_update.message.reply_text.assert_called_once_with("Plugin test enabled.")
  assert "test" in mock_plugins


@pytest.mark.asyncio
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.handlers", new_callable=dict)
@patch("lotb.lotb.application", new_callable=MagicMock)
async def test_disable_plugin(mock_application, mock_handlers, mock_plugins, mock_update, mock_context):
  mock_context.args = ["test"]
  mock_plugins["test"] = MagicMock()
  mock_handlers["test"] = MagicMock()
  await disable_plugin(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Plugin test disabled.")
  assert "test" not in mock_plugins
  assert "test" not in mock_handlers


@pytest.mark.asyncio
@patch("lotb.lotb.plugins", new_callable=dict)
@patch("lotb.lotb.load_plugins")
async def test_list_plugins(mock_load_plugins, mock_plugins, mock_update, mock_context):
  mock_plugins["test"] = MagicMock()
  await list_plugins(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("🤖 Enabled plugins:\ntest")


@pytest.fixture
def plugin():
  return PluginBase(name="test_plugin", description="Test plugin", require_auth=True)


@pytest.fixture
def config():
  return {
    "core": {
      "database": ":memory:",
      "admins": [12345],
    },
    "plugins.test_plugin": {"auth_groups_ids": [67890], "auth_group_enabled": True},
  }


@pytest.fixture
def custom_plugin_config():
  return {"plugins.custom_plugin": {"enabled": True}, "core": {"database": ":memory:"}}


def test_is_authorized_user_authorized_group_not_authorized(plugin, mock_update, config):
  config["plugins.test_plugin"]["auth_groups_ids"] = [11111]
  plugin.set_config(config)
  assert plugin.group_is_authorized(mock_update) is False


def test_is_authorized_user_not_authorized_group_authorized(plugin, mock_update, config):
  config["core"]["admins"] = [54321]
  plugin.set_config(config)
  assert plugin.is_authorized(mock_update) is False


def test_is_authorized_user_and_group_not_authorized(plugin, mock_update, config):
  config["core"]["admins"] = [54321]
  config["plugins.test_plugin"]["auth_groups_ids"] = [11111]
  plugin.set_config(config)
  assert plugin.is_authorized(mock_update) is False and plugin.group_is_authorized(mock_update) is False


def test_is_authorized_group_auth_disabled(plugin, mock_update, config):
  config["plugins.test_plugin"]["auth_group_enabled"] = False
  plugin.set_config(config)
  assert plugin.group_is_authorized(mock_update) is True


def test_plugin_config_enabled_checking():
  test_config = {"plugins.test_plugin": {"enabled": True}}
  plugin_config_key = "plugins.test_plugin"
  plugin_config = test_config.get(plugin_config_key, {})
  assert plugin_config.get("enabled") is True

  test_config = {"plugins.test_plugin": {"enabled": False}}
  plugin_config_key = "plugins.test_plugin"
  plugin_config = test_config.get(plugin_config_key, {})
  assert plugin_config.get("enabled") is False

  test_config = {"plugins.other_plugin": {"enabled": True}}
  plugin_config_key = "plugins.test_plugin"
  plugin_config = test_config.get(plugin_config_key, {})
  assert plugin_config.get("enabled") is None


def test_additional_plugins_directory_nonexistent():
  with patch("lotb.lotb.logger") as mock_logger:
    load_plugins("/nonexistent/directory")
    error_calls = [call for call in mock_logger.error.call_args_list]
    assert len(error_calls) == 0


def test_additional_plugins_file_based_loading(mock_spec_side_effect, custom_plugin_config):
  with patch("lotb.lotb.os.walk") as mock_walk, patch("lotb.lotb.importlib.util.spec_from_file_location") as mock_spec:
    mock_walk.return_value = [("/custom/plugins", [], ["custom_plugin.py", "__init__.py"])]
    mock_spec.side_effect = mock_spec_side_effect
    load_plugins("/custom/plugins", custom_plugin_config)
    mock_spec.assert_called()


def test_additional_plugins_complete_loading(mock_spec_side_effect, custom_plugin_config):
  with (
    patch("lotb.lotb.os.walk") as mock_walk,
    patch("lotb.lotb.importlib.util.spec_from_file_location") as mock_spec,
    patch("lotb.lotb.CommandHandler") as mock_command_handler,
    patch("lotb.lotb.handle_command") as mock_handle_command,
  ):
    mock_walk.return_value = [("/custom/plugins", [], ["custom_plugin.py", "__init__.py"])]
    mock_handler_instance = MagicMock()
    mock_command_handler.return_value = mock_handler_instance
    mock_spec.side_effect = mock_spec_side_effect
    load_plugins("/custom/plugins", custom_plugin_config)
    assert "custom_plugin" in plugins
    assert plugins["custom_plugin"] is not None
    assert "custom_plugin" in handlers
    assert handlers["custom_plugin"] is not None
    mock_command_handler.assert_called_once_with("custom_plugin", mock_handle_command)
