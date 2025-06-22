import random
from typing import List
from typing import Tuple

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


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

    chat_id = update.effective_chat.id

    if update.message and update.message.text:
      message_text = update.message.text.split(maxsplit=1)
      if len(message_text) > 1:
        command = message_text[0]
        term = message_text[1]
      else:
        media_list = self.get_media_list(chat_id)
        if media_list:
          media_names = []
          for name, file_type in media_list:
            ext = {"gif": "gif", "sticker": "stk"}.get(file_type, "img")
            media_names.append(f"{name}.{ext}")
          message = "Saved media:\n" + "\n".join(media_names)
        else:
          message = "No media saved yet, reply to an image with /image <name> to save one"

        await self.reply_message(update, context, message)
        return
    else:
      await self.reply_message(update, context, "Please provide a search term or reply to an image.")
      return

    if command == "/image":
      self.log_info("image save or search request")
      if update.message and update.message.reply_to_message:
        reply_msg = update.message.reply_to_message
        if reply_msg.sticker:
          file_id = reply_msg.sticker.file_id
          file_type = "sticker"
        elif reply_msg.animation:
          file_id = reply_msg.animation.file_id
          file_type = "gif"
        elif reply_msg.photo:
          file_id = reply_msg.photo[-1].file_id
          file_type = "photo"
        else:
          await self.reply_message(update, context, "please reply to an image, gif or sticker to save it")
          return

        name = term
        if self.save_image(chat_id, name, file_id, file_type):
          await self.reply_message(update, context, f"{file_type} saved with name: {name}")
        else:
          await self.reply_message(
            update, context, f"A {file_type} named '{name}' already exists, use a different name."
          )
          self.log_info(f"image with name: {name} already exists for chat {chat_id}, not saving")
        return
      elif self.unsplash_auth:
        self.log_info(f"Searching for image with term: {term}")
        try:
          file_id = await self.search_unsplash_image(term)
          if file_id:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
            return
          else:
            await self.reply_message(update, context, f"No image found for term: {term}")
            return
        except httpx.HTTPStatusError as e:
          if e.response.status_code == 500:
            await self.reply_message(update, context, "error occurred while fetching image from unsplash")
            self.log_info(f"error searching for an image: {term}, HTTP status 500")
            return
          else:
            await self.reply_message(update, context, f"Unexpected error: {e}")
            self.log_info(f"Unexpected error searching for image: {term}, exception: {e}")
      else:
        await self.reply_message(update, context, "Image search is unavailable due to missing Unsplash keys.")

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
    if update.message and update.message.caption and update.message.caption.startswith("/image"):
      message_text = update.message.caption.split(maxsplit=1)
      if len(message_text) > 1:
        name = message_text[1]
      else:
        await self.reply_message(update, context, "Please provide a name for the media.")
        return

      if not update.effective_chat:
        await self.reply_message(update, context, "Chat information is unavailable.")
        return

      match (update.message.sticker, update.message.animation, update.message.photo):
        case (sticker, None, None) if sticker:
          file_id = sticker.file_id
          file_type = "sticker"
        case (None, animation, None) if animation:
          file_id = animation.file_id
          file_type = "gif"
        case (None, None, photo) if photo:
          file_id = photo[-1].file_id
          file_type = "photo"
        case _:
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

    file_id = self.get_image(update.effective_chat.id, name, file_type)
    if file_id:
      if file_type == "photo":
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
      elif file_type == "gif":
        await context.bot.send_animation(chat_id=update.effective_chat.id, animation=file_id)
      elif file_type == "sticker":
        await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=file_id)
    else:
      await self.reply_message(update, context, f"No {file_type} found with name: {name}")

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
