import os
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.common.config import Config
from lotb.plugins.prometheus_alerts import Plugin


@pytest.fixture
def mock_httpx():
  with patch("httpx.AsyncClient") as mock_client:
    yield mock_client


@pytest.fixture
def prometheus_alerts_plugin(mock_db):
  with patch.dict(
    os.environ,
    {
      "LOTB_PLUGIN_PROMETHEUS_ALERTS_PROMETHEUSURL": "http://alertmanager:9093",
      "LOTB_PLUGIN_PROMETHEUS_ALERTS_CHATID": "4815162342",
      "LOTB_PLUGIN_PROMETHEUS_ALERTS_ALERT_INTERVAL": "120",
    },
  ):
    config = Config()
    config.config = {
      "core": {"database": "test.db"},
      "plugins": {
        "prometheus_alerts": {
          "enabled": "true",
          "prometheusUrl": "http://prometheus:9093",
          "chatid": "4815162342",
          "alert_interval": "120",
        }
      },
    }
    plugin = Plugin()
    plugin.set_config(config)
    plugin.connection = mock_db
    plugin.initialize()
    return plugin


@pytest.mark.asyncio
async def test_fetch_prometheus_alerts(prometheus_alerts_plugin, mock_httpx):
  mock_response = MagicMock()
  mock_response.status_code = 200
  mock_response.json.return_value = [{"alertname": "The house is on fire"}]
  mock_httpx.return_value.__aenter__.return_value.get.return_value = mock_response

  alerts = await prometheus_alerts_plugin.fetch_prometheus_alerts()

  assert alerts == [{"alertname": "The house is on fire"}]


@pytest.mark.asyncio
async def test_store_alerts_new_alert(prometheus_alerts_plugin):
  alert = {
    "labels": {"alertname": "The house is on fire", "severity": "critical"},
    "annotations": {"description": "But is is fine fire"},
    "startsAt": "2024-01-01T00:00:00Z",
  }
  mock_cursor = MagicMock()
  mock_cursor.fetchone.return_value = (0,)
  prometheus_alerts_plugin.connection.cursor.return_value = mock_cursor

  new_alerts = prometheus_alerts_plugin.store_alerts([alert])

  assert len(new_alerts) == 1
  mock_cursor.execute.assert_called()


@pytest.mark.asyncio
async def test_store_alerts_existing_alert(prometheus_alerts_plugin):
  alert = {
    "labels": {"alertname": "The house is on fire", "severity": "critical"},
    "annotations": {"description": "But is is fine fire"},
    "startsAt": "2024-01-01T00:00:00Z",
  }
  mock_cursor = MagicMock()
  mock_cursor.fetchone.return_value = (1,)
  prometheus_alerts_plugin.connection.cursor.return_value = mock_cursor

  new_alerts = prometheus_alerts_plugin.store_alerts([alert])

  assert len(new_alerts) == 0
  mock_cursor.execute.assert_called()


@pytest.mark.asyncio
async def test_send_alerts(prometheus_alerts_plugin, mock_context):
  alerts = [
    {
      "labels": {"alertname": "The house is on fire 1", "severity": "critical"},
      "annotations": {"description": "But is is fine fire 1"},
    },
    {
      "labels": {"alertname": "The house is on fire 2", "severity": "warning"},
      "annotations": {"description": "But is is fine fire 2"},
    },
  ]

  await prometheus_alerts_plugin.send_alerts(mock_context, alerts)

  mock_context.bot.send_message.assert_called_once()
  call_args = mock_context.bot.send_message.call_args[1]
  assert call_args["chat_id"] == prometheus_alerts_plugin.chat_id
  assert "The house is on fire 1" in call_args["text"]
  assert "The house is on fire 2" in call_args["text"]


@pytest.mark.asyncio
async def test_fetch_and_store_alerts(prometheus_alerts_plugin, mock_context, mock_httpx):
  mock_response = MagicMock()
  mock_response.status_code = 200
  mock_response.json.return_value = [{"alertname": "The house is on fire"}]
  mock_httpx.return_value.__aenter__.return_value.get.return_value = mock_response

  prometheus_alerts_plugin.store_alerts = MagicMock(return_value=[{"alertname": "The house is on fire"}])
  prometheus_alerts_plugin.send_alerts = AsyncMock()

  await prometheus_alerts_plugin.fetch_and_store_alerts(mock_context)

  prometheus_alerts_plugin.store_alerts.assert_called_once()
  prometheus_alerts_plugin.send_alerts.assert_called_once()


@pytest.mark.asyncio
async def test_execute(mock_update, mock_context, prometheus_alerts_plugin):
  await prometheus_alerts_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("The plugin is running in background.")
