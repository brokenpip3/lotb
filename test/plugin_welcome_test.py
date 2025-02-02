from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from lotb.common.config import Config
from lotb.plugins.welcome import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.welcome": {"enabled": "true"},
  }.get(key, default)
  return config


@pytest.fixture
def mock_update(mock_update):
  update = mock_update
  update.message.text = "/welcome What is dead may never die"
  return update


@pytest.fixture
def welcome_plugin(mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  plugin.reply_message = AsyncMock()
  return plugin


@pytest.mark.asyncio
async def test_welcome_plugin(mock_update, mock_context, welcome_plugin):
  await welcome_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Welcome: What is dead may never die", quote=True)


@pytest.mark.asyncio
async def test_welcome_plugin_no_message(mock_update, mock_context, welcome_plugin):
  mock_update.message.text = "/welcome"
  await welcome_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Welcome!", quote=True)
