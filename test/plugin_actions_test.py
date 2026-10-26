import importlib
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from lotb.common.tools import LocalToolRegistry


def load_plugin(name, tmp_path, user_id):
  plugin = importlib.import_module(f"lotb.plugins.{name}").Plugin()
  config = MagicMock()
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "core.admins": [user_id],
    "plugins.memo": {key: str(tmp_path / key) for key in ["todo", "book", "series", "film", "generic"]},
    "plugins.readwise": {"token": "test"},
  }.get(key, default)
  if name == "memo":
    (tmp_path / "todo").mkdir(exist_ok=True)
    (tmp_path / "generic").mkdir(exist_ok=True)
  plugin.set_config(config)
  with patch("lotb.plugins.readwise.Plugin.check_token_validity", return_value=True):
    plugin.initialize()
  return plugin


@pytest.mark.asyncio
@pytest.mark.parametrize(
  "name,tool,args",
  [
    ("notes", "lotb_notes_add", {"text": "Buy coffee"}),
    ("notes", "lotb_notes_list", {}),
    ("quote", "lotb_quote_add", {}),
    ("memo", "lotb_memo_save", {"text": "Buy coffee", "category": "generic"}),
    ("welcome", "lotb_welcome_send", {"message": "Hello"}),
    ("socialfix", "lotb_socialfix_fix", {"url": "https://x.com/user/status/42"}),
    ("tickets18", "lotb_tickets18_list", {}),
  ],
)
async def test_plugin_tool_actions(name, tool, args, tmp_path, mock_update, mock_context):
  plugin = load_plugin(name, tmp_path, mock_update.effective_user.id)
  mock_update.message.reply_to_message = MagicMock(text="A real quote")
  mock_update.message.reply_to_message.from_user.full_name = "Actual author"
  result = await LocalToolRegistry({name: plugin}).execute(tool, args, mock_update, mock_context)
  assert result.ok, result.error
  if name != "welcome":
    mock_update.message.reply_text.assert_not_awaited()
  if name == "quote":
    assert plugin.db_cursor.execute("SELECT quote FROM quotes").fetchone()[0] == "A real quote\n\n- Actual author"


@pytest.mark.asyncio
async def test_notes_tool_ownership(tmp_path, mock_update, mock_context):
  plugin = load_plugin("notes", tmp_path, mock_update.effective_user.id)
  plugin.execute_query(
    "INSERT INTO notes (user_id, note) VALUES (?, ?)", (mock_update.effective_user.id + 1, "Private")
  )
  registry = LocalToolRegistry({"notes": plugin})
  assert (await registry.execute("lotb_notes_list", {}, mock_update, mock_context)).data["notes"] == []
  assert not (await registry.execute("lotb_notes_delete", {"note_id": 1}, mock_update, mock_context)).ok
  assert plugin.db_cursor.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1
  plugin.admin_ids = []
  assert registry.definitions(mock_update) == []


@pytest.mark.asyncio
async def test_readwise_tool_failure(tmp_path, mock_update, mock_context):
  plugin = load_plugin("readwise", tmp_path, mock_update.effective_user.id)
  with patch("lotb.plugins.readwise.httpx.AsyncClient") as client:
    client.return_value.__aenter__.return_value.post = AsyncMock(return_value=MagicMock(status_code=500))
    result = await LocalToolRegistry({"readwise": plugin}).execute(
      "lotb_readwise_save", {"url": "https://example.com"}, mock_update, mock_context
    )
  assert not result.ok
  assert "Readwise" in result.error
  mock_update.message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["/", "!"])
async def test_notes_command_and_tool_share_actions(prefix, tmp_path, mock_update, mock_context):
  plugin = load_plugin("notes", tmp_path, mock_update.effective_user.id)
  mock_update.message.text = f"{prefix}notes add Buy coffee"
  await plugin.execute(mock_update, mock_context)
  result = await LocalToolRegistry({"notes": plugin}).execute("lotb_notes_list", {}, mock_update, mock_context)
  assert result.data["notes"] == [{"id": 1, "text": "Buy coffee"}]


@pytest.mark.asyncio
async def test_quote_and_subscription_chat_isolation(tmp_path, mock_update, mock_context):
  quote = load_plugin("quote", tmp_path, mock_update.effective_user.id)
  tickets = load_plugin("tickets18", tmp_path, mock_update.effective_user.id)
  quote.execute_query(
    "INSERT INTO quotes (user_id, chat_id, quote) VALUES (?, ?, ?)",
    (mock_update.effective_user.id, mock_update.effective_chat.id + 1, "Other chat"),
  )
  tickets.execute_query(
    "INSERT INTO tickets18_subscriptions (chat_id, venue, weekday) VALUES (?, ?, ?)",
    (mock_update.effective_chat.id + 1, "https://cinema.18tickets.it", "monday"),
  )
  registry = LocalToolRegistry({"quote": quote, "tickets18": tickets})
  assert not (await registry.execute("lotb_quote_random", {}, mock_update, mock_context)).ok
  assert not (await registry.execute("lotb_quote_find", {"term": "Other"}, mock_update, mock_context)).ok
  listed = await registry.execute("lotb_tickets18_list", {}, mock_update, mock_context)
  assert listed.data["subscriptions"] == []
  assert not (await registry.execute("lotb_tickets18_remove", {"subscription_id": 1}, mock_update, mock_context)).ok
  assert tickets.db_cursor.execute("SELECT COUNT(*) FROM tickets18_subscriptions").fetchone()[0] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status,ok", [(200, True), (201, True), (500, False)])
async def test_readwise_tool_outcomes(status, ok, tmp_path, mock_update, mock_context):
  plugin = load_plugin("readwise", tmp_path, mock_update.effective_user.id)
  with patch("lotb.plugins.readwise.httpx.AsyncClient") as client:
    client.return_value.__aenter__.return_value.post = AsyncMock(return_value=MagicMock(status_code=status))
    result = await LocalToolRegistry({"readwise": plugin}).execute(
      "lotb_readwise_save", {"url": "https://example.com"}, mock_update, mock_context
    )
  assert result.ok is ok
  plugin.admin_ids = []
  assert LocalToolRegistry({"readwise": plugin}).definitions(mock_update) == []
