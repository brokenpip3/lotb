from typing import Any
from typing import Dict
from typing import List
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from lotb.common.plugin_class import PluginBase


class ConversationHistory:
  def __init__(self, plugin: "PluginBase", max_history: int):
    self.plugin = plugin
    self.max_history = max_history

  def create_table(self):
    self.plugin.create_table("""
            CREATE TABLE IF NOT EXISTS llm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    self.plugin.execute_query("""
            CREATE INDEX IF NOT EXISTS llm_history_user_chat_idx
            ON llm (user_id, chat_id)
        """)

  def save_message(self, user_id: int, chat_id: int, role: str, content: str) -> None:
    if not self.plugin.db_cursor:
      return

    count = self.plugin.db_cursor.execute(
      "SELECT COUNT(*) FROM llm WHERE user_id = ? AND chat_id = ?", (user_id, chat_id)
    ).fetchone()[0]

    if count >= self.max_history:
      self.plugin.execute_query(
        """
        DELETE FROM llm
        WHERE id IN (
            SELECT id FROM llm
            WHERE user_id = ? AND chat_id = ?
            ORDER BY timestamp ASC
            LIMIT 1
        )
        """,
        (user_id, chat_id),
      )

    truncated_content = content[:2000] if len(content) > 2000 else content
    self.plugin.execute_query(
      "INSERT INTO llm (user_id, chat_id, role, content) VALUES (?, ?, ?, ?)",
      (user_id, chat_id, role, truncated_content),
    )

  def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict[str, Any]]:
    if self.plugin.db_cursor:
      self.plugin.db_cursor.execute(
        "SELECT role, content FROM llm WHERE user_id = ? AND chat_id = ? ORDER BY timestamp ASC",
        (user_id, chat_id),
      )
      return [{"role": row[0], "content": row[1]} for row in self.plugin.db_cursor.fetchall()]
    return []

  def clear_history(self, user_id: int, chat_id: int) -> None:
    if not self.plugin.db_cursor:
      return

    self.plugin.execute_query("DELETE FROM llm WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
