from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.common.config import Config
from lotb.plugins.readwise import Plugin


@pytest.fixture
def mock_update(mock_update):
  update = mock_update
  update.message.text = "/readwise https://wikipedia.com"
  return update


@pytest.mark.asyncio
async def test_readwise_token_not_found():
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.readwise": {"enabled": "true"},
  }.get(key, default)
  plugin = Plugin()
  plugin.set_config(config)
  with pytest.raises(ValueError, match="Readwise token not found in configuration."):
    plugin.initialize()


def test_extract_url_from_message():
  plugin = Plugin()
  assert plugin.extract_url_from_message("this is a local url http://local.lan") == "http://local.lan"
  assert plugin.extract_url_from_message("I love wikipedia: https://wikipedia.com") == "https://wikipedia.com"
  assert plugin.extract_url_from_message("No url here") == ""


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.readwise": {"enabled": "true", "token": "fake_token"},
  }.get(key, default)
  return config


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_save_url(mock_httpx_client, mock_httpx_async, mock_update, mock_context, mock_config):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid

  mock_response_save = MagicMock()
  mock_response_save.status_code = 201
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_save

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("URL saved to Readwise successfully.", quote=True)


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_article_already_exist(
  mock_httpx_client, mock_httpx_async, mock_update, mock_context, mock_config
):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid

  mock_response_already_present = MagicMock()
  mock_response_already_present.status_code = 200
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_already_present

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("URL already exists in your Readwise archive.", quote=True)


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_invalid_token(mock_httpx_client, mock_config):
  mock_response_invalid = MagicMock()
  mock_response_invalid.status_code = 401
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_invalid

  with pytest.raises(ValueError, match="Readwise token is not valid."):
    plugin = Plugin()
    plugin.set_config(mock_config)
    plugin.initialize()


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_no_url(mock_httpx_client, mock_httpx_async, mock_update, mock_context, mock_config):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid

  mock_response_save = MagicMock()
  mock_response_save.status_code = 201
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_save

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  mock_update.message.text = "/readwise"
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Missing URL argument for Readwise command.", quote=True)


@pytest.mark.asyncio
@patch("lotb.plugins.readwise.httpx.AsyncClient")
@patch("lotb.plugins.readwise.httpx.Client")
async def test_readwise_failed_to_save(mock_httpx_client, mock_httpx_async, mock_update, mock_context, mock_config):
  mock_response_valid = MagicMock()
  mock_response_valid.status_code = 204
  mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response_valid
  mock_response_fail = MagicMock()
  mock_response_fail.status_code = 500
  mock_httpx_async.return_value.__aenter__.return_value.post.return_value = mock_response_fail

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Failed to save URL to Readwise.", quote=True)
