from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import LocalToolRegistry
from lotb.common.tools import PluginTool
from lotb.common.tools import ToolResult


@pytest.fixture
def tool_plugin():
  plugin = PluginBase("example", "example")
  plugin.get_tools = lambda: [
    PluginTool(
      "lotb_example_delete",
      "Delete one item",
      {
        "type": "object",
        "properties": {"id": {"type": "integer", "minimum": 1}},
        "required": ["id"],
        "additionalProperties": False,
      },
      plugin.action,
    )
  ]
  plugin.action = AsyncMock(return_value=ToolResult(True, {"deleted": True}))
  return plugin


@pytest.mark.asyncio
async def test_registry_live_permissions(tool_plugin, mock_update, mock_context):
  plugins = {"example": tool_plugin}
  registry = LocalToolRegistry(plugins)
  assert registry.definitions(mock_update)[0]["function"]["name"] == "lotb_example_delete"
  tool_plugin.auth_group_enabled = True
  assert registry.definitions(mock_update) == []
  result = await registry.execute("lotb_example_delete", {"id": 1}, mock_update, mock_context)
  assert not result.ok
  tool_plugin.action.assert_not_awaited()
  tool_plugin.auth_group_enabled = False
  result = await registry.execute("lotb_example_delete", {"id": 1}, mock_update, mock_context)
  assert result.ok
  plugins.clear()
  assert registry.definitions(mock_update) == []
  assert not (await registry.execute("lotb_example_delete", {"id": 1}, mock_update, mock_context)).ok


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [{}, {"id": 0}, {"id": True}, {"id": "1"}, {"id": 1, "chat_id": 5}, [], None])
async def test_registry_rejects_invalid_arguments(arguments, tool_plugin, mock_update, mock_context):
  registry = LocalToolRegistry({"example": tool_plugin})
  assert not (await registry.execute("lotb_example_delete", arguments, mock_update, mock_context)).ok
  tool_plugin.action.assert_not_awaited()


@pytest.mark.parametrize("missing", ["effective_chat", "effective_user"])
def test_registry_requires_identity(missing, tool_plugin, mock_update):
  setattr(mock_update, missing, None)
  assert LocalToolRegistry({"example": tool_plugin}).definitions(mock_update) == []


def test_registry_duplicate_names(tool_plugin, mock_update):
  other = MagicMock()
  other.get_tools.return_value = tool_plugin.get_tools()
  with pytest.raises(ValueError, match="Duplicate"):
    LocalToolRegistry({"one": tool_plugin, "two": other}).definitions(mock_update)
