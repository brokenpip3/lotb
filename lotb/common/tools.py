from dataclasses import asdict
from dataclasses import dataclass
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import TYPE_CHECKING

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
  from lotb.common.plugin_class import PluginBase


@dataclass
class ToolResult:
  ok: bool
  data: dict[str, Any]
  error: str | None = None
  sent_message: bool = False

  def as_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class PluginTool:
  name: str
  description: str
  parameters: dict[str, Any]
  handler: Callable[[Update, ContextTypes.DEFAULT_TYPE, dict[str, Any]], Awaitable[ToolResult]]

  def definition(self) -> dict[str, Any]:
    return {
      "type": "function",
      "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
    }


def plugin_tool(name: str, description: str, properties: dict[str, Any], action: Callable) -> PluginTool:
  async def handler(update, context, arguments):
    return await action(update, context, **arguments)

  return PluginTool(
    name,
    description,
    {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False},
    handler,
  )


class LocalToolRegistry:
  def __init__(self, plugins: dict[str, "PluginBase"]):
    self.plugins = plugins

  def _tools(self):
    tools = {}
    for plugin in list(self.plugins.values()):
      for tool in plugin.get_tools():
        if not tool.name.startswith("lotb_"):
          raise ValueError(f"Local tool must start with lotb_: {tool.name}")
        if tool.name in tools:
          raise ValueError(f"Duplicate local tool: {tool.name}")
        Draft202012Validator.check_schema(tool.parameters)
        tools[tool.name] = (plugin, tool)
    return tools

  @staticmethod
  def _authorized(plugin, update):
    return (
      update.effective_user is not None
      and update.effective_chat is not None
      and plugin.group_is_authorized(update)
      and plugin.is_authorized(update)
    )

  def definitions(self, update: Update) -> list[dict[str, Any]]:
    return [tool.definition() for plugin, tool in self._tools().values() if self._authorized(plugin, update)]

  async def execute(self, name: str, arguments: dict[str, Any], update: Update, context) -> ToolResult:
    entry = self._tools().get(name)
    if entry is None:
      return ToolResult(False, {}, "Unknown or disabled local tool")
    plugin, tool = entry
    if not self._authorized(plugin, update):
      return ToolResult(False, {}, "Not authorized for this plugin")
    try:
      Draft202012Validator(tool.parameters).validate(arguments)
    except ValidationError as error:
      return ToolResult(False, {}, f"Invalid tool arguments: {error.message}")
    try:
      return await tool.handler(update, context, arguments)
    except Exception as error:
      plugin.log_error(f"Local tool {name} failed: {error}")
      return ToolResult(False, {}, f"Action failed: {error}")
