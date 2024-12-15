import random

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from lotb.common.plugin_class import PluginBase


class Plugin(PluginBase):
  def __init__(self):
    super().__init__("image", "Save and recall images with /image <name> and <name>.img", require_auth=False)

  def initialize(self):
    self.initialize_plugin()
    self.create_table("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                file_id TEXT NOT NULL
            )
        """)
    self.pattern_actions = {
      r"\b(\w+)\.img\b": self.recall_image,
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
    if update.message and update.message.text:
      message_text = update.message.text.split(maxsplit=1)
      if len(message_text) > 1:
        command = message_text[0]
        term = message_text[1]
      else:
        await self.reply_message(update, context, "Please provide a search term or reply to an image.")
        return
    else:
      await self.reply_message(update, context, "Please provide a search term or reply to an image.")
      return

    if update.effective_chat:
      chat_id = update.effective_chat.id
    else:
      await self.reply_message(update, context, "Chat information is unavailable.")
      return

    if command == "/image":
      self.log_info("Image save or search request.")
      if update.message and update.message.reply_to_message and update.message.reply_to_message.photo:
        file_id = update.message.reply_to_message.photo[-1].file_id
        name = term  # Use the provided term as the name
        self.save_image(chat_id, name, file_id)
        await self.reply_message(update, context, f"Image saved with name: {name}")
      elif self.unsplash_auth:
        # Search on Unsplash if it's a term and no image is quoted
        self.log_info(f"Searching for image with term: {term}")
        try:
          file_id = await self.search_unsplash_image(term)
          if file_id:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
          else:
            await self.reply_message(update, context, f"No image found for term: {term}")
        except httpx.HTTPStatusError as e:
          if e.response.status_code == 500:
            if update.message:
              await update.message.reply_text("error occurred while fetching image from unsplash")
            self.log_info(f"error searching for an image: {term}, HTTP status 500")
          else:
            await update.message.reply_text(f"Unexpected error: {e}")
            self.log_info(f"Unexpected error searching for image: {term}, exception: {e}")
      else:
        await self.reply_message(update, context, "Image search is unavailable due to missing Unsplash keys.")

  def save_image(self, chat_id: int, name: str, file_id: str):
    self.execute_query("INSERT INTO images (chat_id, name, file_id) VALUES (?, ?, ?)", (chat_id, name, file_id))
    self.log_info(f"Image saved for chat {chat_id} with name: {name} and file_id: {file_id}")

  async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.caption and update.message.caption.startswith("/image"):
      message_text = update.message.caption.split(maxsplit=1)
      if len(message_text) > 1:
        name = message_text[1]
      else:
        await self.reply_message(update, context, "Please provide a name for the image.")
        return

      if update.message and update.message.photo:
        file_id = update.message.photo[-1].file_id
        if update.effective_chat:
          self.save_image(update.effective_chat.id, name, file_id)
          await self.reply_message(update, context, f"Image saved with name: {name}")
        else:
          await self.reply_message(update, context, "Chat information is unavailable.")
      else:
        await self.reply_message(update, context, "No photo found in the message.")
      await self.reply_message(update, context, f"Image saved with name: {name}")

  async def recall_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
      message_text = update.message.text
      name = message_text.split(".img")[0]
    else:
      await self.reply_message(update, context, "Message text is unavailable.")
      return

    if update.effective_chat:
      chat_id = update.effective_chat.id
    else:
      await self.reply_message(update, context, "Chat information is unavailable.")
      return
    file_id = self.get_image(chat_id, name)
    if file_id:
      await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
    else:
      await self.reply_message(update, context, f"No image found with name: {name}")

  def get_image(self, chat_id: int, name: str) -> str:
    if self.db_cursor:
      self.db_cursor.execute("SELECT file_id FROM images WHERE chat_id = ? AND name = ?", (chat_id, name))
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
