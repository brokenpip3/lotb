from contextlib import asynccontextmanager
from functools import wraps
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import TYPE_CHECKING

from litellm.experimental_mcp_client import load_mcp_tools
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

if TYPE_CHECKING:
  from lotb.common.plugin_class import PluginBase


class MCPSessionManager:
  def __init__(self, plugin: "PluginBase"):
    self.plugin = plugin

  @asynccontextmanager
  async def session_context(self, server_cfg: Dict[str, Any]):
    try:
      async with self.get_mcp_session(server_cfg) as ctx:
        read, write, _ = ctx
        async with ClientSession(read, write) as session:
          await session.initialize()
          yield session
    except Exception as e:
      self.plugin.log_warning(f"MCP session failed for {server_cfg.get('name', 'unknown')}: {e}")
      raise

  def get_mcp_session(self, server_cfg: Dict[str, Any]):
    return streamablehttp_client(
      url=server_cfg["url"] + "/mcp", headers={"Authorization": f"Bearer {server_cfg['auth_value']}"}
    )

  @staticmethod
  def with_session(operation_name: str, default_return=None):
    def decorator(func):
      @wraps(func)
      async def wrapper(plugin_self, server_cfg: Dict[str, Any], *args, **kwargs):
        session_manager = MCPSessionManager(plugin_self.plugin)
        try:
          async with session_manager.session_context(server_cfg) as session:
            plugin_self.plugin.log_info(f"executing {operation_name} on {server_cfg['name']}")
            result = await func(plugin_self, session, server_cfg, *args, **kwargs)
            plugin_self.plugin.log_info(f"{operation_name} completed on {server_cfg['name']}")
            return result
        except Exception as e:
          plugin_self.plugin.log_warning(f"failed {operation_name} on {server_cfg['name']}: {e}")
          return default_return if default_return is not None else []

      return wrapper

    return decorator


class MCPManager:
  def __init__(self, plugin: "PluginBase", servers: List[Dict[str, Any]]):
    self.plugin = plugin
    self.servers = servers
    self.session_manager = MCPSessionManager(plugin)
    self.tool_to_server_map: Dict[str, Dict[str, Any]] = {}
    self.resource_to_server_map: Dict[str, Dict[str, Any]] = {}

  @MCPSessionManager.with_session("loading tools", [])
  async def list_tools(self, session: ClientSession, server_cfg: Dict[str, Any]) -> List[Any]:
    tools = await load_mcp_tools(session=session, format="openai")
    self.plugin.log_info(
      f"loaded {len(tools)} tools from {server_cfg['name']}: "
      f"{[t.get('function', {}).get('name', 'unknown') for t in tools if t.get('type') == 'function']}"  # type: ignore
    )
    return tools

  @MCPSessionManager.with_session("loading resources", [])
  async def list_resources(self, session: ClientSession, server_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    resources_response = await session.list_resources()
    resources = []

    if hasattr(resources_response, "resources"):
      for resource in resources_response.resources:
        resources.append(
          {
            "uri": str(resource.uri),
            "name": getattr(resource, "name", ""),
            "description": getattr(resource, "description", ""),
            "mimeType": getattr(resource, "mimeType", ""),
          }
        )

    self.plugin.log_info(
      f"loaded {len(resources)} resources from {server_cfg['name']}: "
      f"{[r.get('name', r.get('uri', 'unknown')) for r in resources]}"
    )
    return resources

  async def load_all_items(self, item_type: str, loader_func: Callable, mapper_func: Callable) -> List[Dict[str, Any]]:
    self.plugin.log_info(f"loading all {item_type} from {len(self.servers)} servers")
    all_items = []
    server_map = getattr(self, f"{item_type[:-1]}_to_server_map")

    for i, server in enumerate(self.servers):
      self.plugin.log_info(f"processing server {i + 1}/{len(self.servers)}: {server.get('name', 'unknown')}")
      items = await loader_func(server)
      mapped_count = mapper_func(items, server, server_map)

      self.plugin.log_info(
        f"server '{server.get('name', 'unknown')}' contributed {len(items)} {item_type} ({mapped_count} mapped)"
      )
      all_items.extend(items)

    self.plugin.log_info(f"total {item_type} loaded: {len(all_items)}, total mappings: {len(server_map)}")
    return all_items

  def _map_tools(self, tools: List[Dict[str, Any]], server: Dict[str, Any], server_map: Dict[str, Any]) -> int:
    count = 0
    for tool in tools:
      if tool.get("type") == "function":
        tool_name = tool["function"]["name"]
        server_map[tool_name] = server
        count += 1
        self.plugin.log_info(f"mapped tool '{tool_name}' to server '{server.get('name', 'unknown')}'")
    return count

  def _map_resources(self, resources: List[Dict[str, Any]], server: Dict[str, Any], server_map: Dict[str, Any]) -> int:
    count = 0
    for resource in resources:
      if uri := resource.get("uri"):
        server_map[uri] = server
        count += 1
        self.plugin.log_info(f"mapped resource '{uri}' to server '{server.get('name', 'unknown')}'")
    return count

  async def load_all_tools(self) -> List[Dict[str, Any]]:
    return await self.load_all_items("tools", self.list_tools, self._map_tools)

  async def load_all_resources(self) -> List[Dict[str, Any]]:
    return await self.load_all_items("resources", self.list_resources, self._map_resources)
