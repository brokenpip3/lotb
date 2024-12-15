import os
from unittest.mock import patch

import pytest

from lotb.common.config import Config


@pytest.fixture
def mock_toml_file(tmp_path):
  toml_content = """
    [core]
    token = "test_token"
    database = "/tmp/test.db"

    [plugins.readwise]
    token = "readwise_token"

    [plugins.rssfeed]
    chatid = "4815162342"
    interval = 40
    feeds = [
        {name = "San-ti-feed", url = "https://youarebugs.alien"},
        {name = "Asoiaf-feed2", url = "https://not.today"}
    ]
    """
  config_file = tmp_path / "config.toml"
  config_file.write_text(toml_content)
  yield str(config_file)


@pytest.fixture
def mock_env_vars():
  with patch.dict(
    os.environ,
    {
      "LOTB_CORE_TOKEN": "env_test_token",
      "LOTB_CORE_DATABASE": "env_test.db",
      "LOTB_PLUGINS_READWISE_TOKEN": "env_readwise_token",
      "LOTB_PLUGINS_RSSFEED_CHATID": "env_4815162342",
      "LOTB_PLUGINS_RSSFEED_INTERVAL": "40",
    },
  ):
    yield


def test_load_config_from_file(mock_toml_file):
  with patch("os.path.exists", return_value=True):
    config = Config(mock_toml_file)
    assert config.get("core.token") == "test_token"
    assert config.get("core.database") == "/tmp/test.db"
    assert config.get("plugins.readwise.token") == "readwise_token"
    assert config.get("plugins.rssfeed.chatid") == "4815162342"
    assert config.get("plugins.rssfeed.interval") == 40
    assert config.get("plugins.rssfeed.feeds")[0]["name"] == "San-ti-feed"


def test_load_config_from_env(mock_env_vars, tmp_path):
  config_file = tmp_path / "config.toml"
  config_file.write_text("")
  config = Config(str(config_file))
  assert config.get("core.token") == "env_test_token"
  assert config.get("core.database") == "env_test.db"
  assert config.get("plugins.readwise.token") == "env_readwise_token"
  assert config.get("plugins.rssfeed.chatid") == "env_4815162342"
  assert int(config.get("plugins.rssfeed.interval")) == 40


def test_env_vars_override_file(mock_toml_file, mock_env_vars):
  with patch("os.path.exists", return_value=True):
    config = Config(mock_toml_file)
    assert config.get("core.token") == "env_test_token"
    assert config.get("core.database") == "env_test.db"
    assert config.get("plugins.readwise.token") == "env_readwise_token"
    assert config.get("plugins.rssfeed.chatid") == "env_4815162342"
    assert int(config.get("plugins.rssfeed.interval")) == 40


def test_default_value(tmp_path):
  config_file = tmp_path / "config.toml"
  config_file.write_text("")  # Empty config file
  config = Config(str(config_file))
  assert config.get("nonexistent.key", "default_value") == "default_value"
