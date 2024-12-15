import pytest

from lotb.plugins.welcome import Plugin


@pytest.fixture
def mock_update(mock_update):
  update = mock_update
  update.message.text = "/welcome What is dead may never die"
  return update


@pytest.mark.asyncio
async def test_welcome_plugin(mock_update, mock_context):
  plugin = Plugin()
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Welcome: What is dead may never die", quote=True)


@pytest.mark.asyncio
async def test_welcome_plugin_no_message(mock_update, mock_context):
  plugin = Plugin()
  mock_update.message.text = "/welcome"
  await plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Welcome!", quote=True)
