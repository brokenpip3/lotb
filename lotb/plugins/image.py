import random
from typing import List
from typing import Tuple

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase
from lotb.common.tools import plugin_tool
from lotb.common.tools import ToolResult


class Plugin(PluginBase):
  def __init__(self):
    super().__init__(
      "image",
      "Save media with /image <name> and recall them with <name>.<type> \n search for images using /image <term>, if no term passed list all the saved media.\n supported media: img, gif, sticker(stk)",
      require_auth=False,
    )

  def initialize(self):
    self.initialize_plugin()

    self.create_table("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL
        )
    """)

    # trigger migration from previous plugin versions
    try:
      self.db_cursor.execute("SELECT file_type FROM images LIMIT 1")
    except Exception:
      self.log_info("migrating 001: images table add file_type column")
      self.db_cursor.execute("ALTER TABLE images ADD COLUMN file_type TEXT NOT NULL DEFAULT 'photo'")
      self.db_cursor.execute("UPDATE images SET file_type = 'photo' WHERE file_type IS NULL")

    self.execute_query("CREATE INDEX IF NOT EXISTS images_chat_id_index ON images (chat_id)")
    self.pattern_actions = {
      r"\b(\w+)\.img\b": self.recall_image,
      r"\b(\w+)\.gif\b": self.recall_image,
      r"\b(\w+)\.stk\b": self.recall_image,
    }
    plugin_config = self.config.get(f"plugins.{self.name}", {})

    self.unsplash_access_key = plugin_config.get("accesskey")
    self.unsplash_secret_key = plugin_config.get("secretkey")
    if not self.unsplash_access_key or not self.unsplash_secret_key:
      self.log_warning("Unsplash access key and/or secret key not provided. Image search will be unavailable.")
      self.unsplash_access_key = None
      self.unsplash_secret_key = None
      self.unsplash_auth = None
    else:
      self.unsplash_auth = {
        "Authorization": f"Client-ID {self.unsplash_access_key}",
        "Secret-Key": self.unsplash_secret_key,
      }

    self.log_info("Images plugin initialized and table created.")

  async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      await self.reply_message(update, context, "Chat information is unavailable.")
      return

    if update.message and update.message.text:
      message_text = update.message.text.split(maxsplit=1)
      if len(message_text) > 1:
        command = message_text[0]
        term = message_text[1]
      else:
        media_result = await self.list_media_action(update, context)
        media_list = [(item["name"], item["media_type"]) for item in media_result.data["media"]]
        if media_list:
          media_groups: dict[str, list[str]] = {}
          for name, file_type in media_list:
            if file_type not in media_groups:
              media_groups[file_type] = []
            media_groups[file_type].append(name)
          message = "📁 Saved media:\n"
          type_order = ["photo", "gif", "sticker"]

          for file_type in type_order:
            if file_type in media_groups:
              type_name = {"photo": "📷 images", "gif": "🎬 gif", "sticker": "🖼️ stickers"}[file_type]
              message += f"\n{type_name}:\n"
              message += "\n".join([f"  • {name}" for name in sorted(media_groups[file_type])])
        else:
          message = "No media saved yet, reply to an image with /image <name> to save one"

        await self.reply_message(update, context, message)
        return
    else:
      await self.reply_message(update, context, "Please provide a search term or reply to an image.")
      return

    if command.lstrip("/!").split("@", 1)[0] == "image":
      self.log_info("image save or search request")
      if update.message and update.message.reply_to_message:
        result = await self.save_media_action(update, context, term)
      else:
        result = await self.search_media_action(update, context, term)
      if not result.sent_message:
        await self.reply_message(
          update, context, result.data["message"] if result.ok else result.error or "Image action failed"
        )

  def get_tools(self):
    text = {"type": "string", "minLength": 1}
    return [
      plugin_tool("lotb_image_list", "List saved media in this chat", {}, self.list_media_action),
      plugin_tool(
        "lotb_image_send",
        "Send saved media from this chat",
        {"name": text, "media_type": {"type": "string", "enum": ["photo", "gif", "sticker"]}},
        self.send_media_action,
      ),
      plugin_tool("lotb_image_search", "Search Unsplash and send a photo", {"query": text}, self.search_media_action),
      plugin_tool(
        "lotb_image_save", "Save the actual replied-to photo, GIF or sticker", {"name": text}, self.save_media_action
      ),
    ]

  async def list_media_action(self, update, context) -> ToolResult:
    media = self.get_media_list(update.effective_chat.id)
    return ToolResult(True, {"media": [{"name": name, "media_type": kind} for name, kind in media]})

  async def save_media_action(self, update, context, name: str) -> ToolResult:
    reply = update.message.reply_to_message if update.message else None
    if not reply:
      return ToolResult(False, {}, "please reply to an image, gif or sticker to save it")
    if reply.sticker:
      file_id, kind = reply.sticker.file_id, "sticker"
    elif reply.animation:
      file_id, kind = reply.animation.file_id, "gif"
    elif reply.photo:
      file_id, kind = reply.photo[-1].file_id, "photo"
    else:
      return ToolResult(False, {}, "please reply to an image, gif or sticker to save it")
    if not self.save_image(update.effective_chat.id, name, file_id, kind):
      return ToolResult(False, {}, f"A {kind} named '{name}' already exists, use a different name.")
    return ToolResult(True, {"message": f"{kind} saved with name: {name}"})

  async def send_media_action(self, update, context, name: str, media_type: str) -> ToolResult:
    file_id = self.get_image(update.effective_chat.id, name, media_type)
    if not file_id:
      return ToolResult(False, {}, f"No {media_type} found with name: {name}")
    if media_type == "photo":
      await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
    elif media_type == "gif":
      await context.bot.send_animation(chat_id=update.effective_chat.id, animation=file_id)
    elif media_type == "sticker":
      await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=file_id)
    else:
      return ToolResult(False, {}, "Unsupported media type")
    return ToolResult(True, {"message": f"Sent {media_type}: {name}"}, sent_message=True)

  async def search_media_action(self, update, context, query: str) -> ToolResult:
    if not self.unsplash_auth:
      return ToolResult(False, {}, "Image search is unavailable due to missing Unsplash keys.")
    try:
      url = await self.search_unsplash_image(query)
      if not url:
        return ToolResult(False, {}, f"No image found for term: {query}")
      await context.bot.send_photo(chat_id=update.effective_chat.id, photo=url)
      return ToolResult(True, {"message": f"Sent a photo for: {query}"}, sent_message=True)
    except httpx.HTTPStatusError as error:
      message = (
        "error occurred while fetching image from unsplash"
        if error.response.status_code == 500
        else f"Unexpected error: {error}"
      )
      return ToolResult(False, {}, message)

  def save_image(self, chat_id: int, name: str, file_id: str, file_type: str) -> bool:
    existing = self.get_image(chat_id, name, file_type)
    if existing:
      return False

    self.execute_query(
      "INSERT INTO images (chat_id, name, file_id, file_type) VALUES (?, ?, ?, ?)", (chat_id, name, file_id, file_type)
    )
    self.log_info(f"image saved for chat {chat_id} with name: {name}, type: {file_type} and file_id: {file_id}")
    return True

  async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (
      update.message and update.message.caption and update.message.caption.split(maxsplit=1)[0] in ("/image", "!image")
    ):
      message_text = update.message.caption.split(maxsplit=1)
      if len(message_text) > 1:
        name = message_text[1]
      else:
        await self.reply_message(update, context, "Please provide a name for the media.")
        return

      if not update.effective_chat:
        await self.reply_message(update, context, "Chat information is unavailable.")
        return

      if update.message.sticker:
        file_id, file_type = update.message.sticker.file_id, "sticker"
      elif update.message.animation:
        file_id, file_type = update.message.animation.file_id, "gif"
      elif update.message.photo:
        file_id, file_type = update.message.photo[-1].file_id, "photo"
      else:
        await self.reply_message(update, context, "No media found in the message.")
        return

      if self.save_image(update.effective_chat.id, name, file_id, file_type):
        await self.reply_message(update, context, f"Saved with name: {name}")
      else:
        await self.reply_message(update, context, f"A {file_type} named '{name}' already exists, use a different name.")

  async def recall_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
      message_text = update.message.text
      match message_text.split("."):
        case [name, "img"]:
          file_type = "photo"
        case [name, "gif"]:
          file_type = "gif"
        case [name, "stk"]:
          file_type = "sticker"
        case _:
          return
    else:
      await self.reply_message(update, context, "Message text is unavailable.")
      return

    if not update.effective_chat:
      await self.reply_message(update, context, "Chat information is unavailable.")
      return

    result = await self.send_media_action(update, context, name, file_type)
    if not result.ok:
      await self.reply_message(update, context, result.error or "Action failed")

  def get_media_list(self, chat_id: int) -> List[Tuple[str, str]]:
    if self.db_cursor:
      self.db_cursor.execute("SELECT name, file_type FROM images WHERE chat_id = ?", (chat_id,))
      return self.db_cursor.fetchall()
    return []

  def get_image(self, chat_id: int, name: str, file_type: str) -> str:
    if self.db_cursor:
      self.db_cursor.execute(
        "SELECT file_id FROM images WHERE chat_id = ? AND name = ? AND file_type = ?", (chat_id, name, file_type)
      )
      result = self.db_cursor.fetchone()
      if result:
        return result[0]
    return ""

  async def search_unsplash_image(self, term: str):
    url = f"https://api.unsplash.com/photos/random?query={term}&client_id={self.unsplash_access_key}&count=10"
    async with httpx.AsyncClient() as client:
      response = await client.get(url, headers=self.unsplash_auth)
      if response.status_code == 200:
        images = response.json()
        if images:
          random_image = random.choice(images)
          return random_image["urls"]["regular"]
      return None
