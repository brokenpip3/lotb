import argparse
import importlib.util
import logging
import os
from pathlib import Path

from telegram import BotCommand
from telegram import Update
from telegram.ext import Application
from telegram.ext import CommandHandler
from telegram.ext import ContextTypes
from telegram.ext import filters
from telegram.ext import MessageHandler

from lotb.common.config import Config

# see: https://github.com/encode/httpx/discussions/2765
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.CRITICAL)

log_level = logging.DEBUG if os.getenv("LOTB_DEBUG") else logging.INFO
logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("lotb")

plugins = {}
handlers = {}
application = None


def load_plugins(directory, config=None):
  plugins_path = Path(directory)
  for root, _, files in os.walk(plugins_path):
    for file in files:
      if file.endswith(".py") and file != "__init__.py":
        module_name = file[:-3]

        plugin_config_key = f"plugins.{module_name}"
        plugin_config = config.get(plugin_config_key, {}) if config else {}
        if not plugin_config.get("enabled", False):
          logger.info(f"Skipping disabled plugin: {module_name}")
          continue
        try:
          file_path = Path(root) / file
          spec = importlib.util.spec_from_file_location(module_name, file_path)
          if spec is None:
            logger.error(f"Failed to create spec for plugin {module_name} from {file_path}")
            continue
          module = importlib.util.module_from_spec(spec)
          spec.loader.exec_module(module)
          plugin_instance = module.Plugin()
          logger.debug(f"Setting config for plugin: {module_name}")
          plugin_instance.set_config(config)
          if hasattr(plugin_instance, "initialize"):
            plugin_instance.initialize()
          plugins[module_name] = plugin_instance
          handlers[module_name] = CommandHandler(module_name, handle_command)
          logger.info(f"Loaded plugin: {module_name}")
        except Exception as e:
          logger.error(f"Failed to load plugin {module_name}: {e}")


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.message and update.message.text:
    command = update.message.text.split()[0][1:]
  else:
    logger.warning("Received a command update with no message text.")
    return
  if command in plugins:
    plugin = plugins[command]
    if not plugin.group_is_authorized(update):
      if update.effective_chat:
        logger.warning(f"unauthorized access attempt to command '{command}' in chat {update.effective_chat.id}")
      return
    if plugin.is_authorized(update):
      await plugin.execute(update, context)
    else:
      if update.message:
        await update.message.reply_text("you are not authorized to use this command.")
      if update.effective_user and update.effective_chat:
        logger.warning(
          f"Unauthorized access to command: {command} by user {update.effective_user.id} in chat {update.effective_chat.id}"
        )
  else:
    if update.message:
      await update.message.reply_text("command not found.")
    logger.warning(f"Command not found: {command}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  for plugin in plugins.values():
    if await plugin.intercept_patterns(update, context, plugin.pattern_actions):
      return


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
  for plugin in plugins.values():
    if hasattr(plugin, "handle_media"):
      await plugin.handle_media(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  commands = [f"/{command} - {plugin.description}" for command, plugin in plugins.items()]
  response = "Available commands:\n\n" + "\n".join(commands) + "\n\nFind more at https://github.com/brokenpip3/lotb"
  if update.message:
    await update.message.reply_text(response, disable_web_page_preview=True)
    logger.info("Displayed help commands.")


async def enable_plugin(update: Update, context: ContextTypes.DEFAULT_TYPE, config):
  if context.args and len(context.args) == 1:
    plugin_name = context.args[0]
    if plugin_name not in plugins:
      module_path = f"lotb.plugins.{plugin_name}"
      try:
        module = importlib.import_module(module_path)
        plugin_instance = module.Plugin()
        plugin_instance.set_config(config)
        if hasattr(plugin_instance, "initialize"):
          plugin_instance.initialize()
        plugins[plugin_name] = plugin_instance
        handler = CommandHandler(plugin_name, handle_command)
        handlers[plugin_name] = handler
        if application:
          application.add_handler(handler)
        if update.message:
          await update.message.reply_text(f"Plugin {plugin_name} enabled.")
        logger.info(f"Plugin {plugin_name} enabled.")
      except Exception as e:
        if update.message:
          await update.message.reply_text(f"Failed to enable plugin {plugin_name}: {e}")
        logger.error(f"Failed to enable plugin {plugin_name}: {e}")
    else:
      if update.message:
        await update.message.reply_text(f"Plugin {plugin_name} is already enabled.")
      logger.warning(f"Plugin {plugin_name} is already enabled.")
  else:
    if update.message:
      await update.message.reply_text("Usage: /enable <plugin_name>")


async def disable_plugin(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if context.args and len(context.args) == 1:
    plugin_name = context.args[0]
    if plugin_name in plugins:
      if application:
        application.remove_handler(handlers[plugin_name])
      del plugins[plugin_name]
      del handlers[plugin_name]
      if update.message:
        await update.message.reply_text(f"Plugin {plugin_name} disabled.")
      logger.info(f"Plugin {plugin_name} disabled.")
    else:
      if update.message:
        await update.message.reply_text(f"Plugin {plugin_name} is not enabled.")
      logger.warning(f"Plugin {plugin_name} is not enabled.")
  else:
    if update.message:
      await update.message.reply_text("Usage: /disable <plugin_name>")


async def list_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE):
  enabled_plugins = "\n⚙️".join(plugins.keys())
  if update.message:
    await update.message.reply_text(f"🤖 Enabled plugins:\n{enabled_plugins}")
  logger.info("Listed enabled plugins.")


async def post_init(application: Application) -> None:
  commands = [
    BotCommand("help", "Display help message"),
    BotCommand("enable", "Enable a plugin"),
    BotCommand("disable", "Disable a plugin"),
    BotCommand("plugins", "List enabled plugins"),
  ]

  for command, plugin in plugins.items():
    commands.append(BotCommand(command, plugin.description))
  await application.bot.set_my_commands(commands)


def main():
  parser = argparse.ArgumentParser(description="LOTB Bot")
  parser.add_argument("--config", required=True, help="Path to the configuration file")
  args = parser.parse_args()

  global config
  config = Config(args.config)

  logger.debug(f"Config loaded: {config.config}")

  token = config.get("core.token")
  if not token:
    logger.error("Telegram bot token not found in the config file")
    return

  global application
  application = Application.builder().token(token).post_init(post_init).build()

  default_plugins_dir = Path(__file__).parent / "plugins"
  load_plugins(default_plugins_dir, config)

  additional_plugins_dir = config.get("core.plugins_additional_directory")
  if additional_plugins_dir:
    load_plugins(additional_plugins_dir, config)

  for command, handler in handlers.items():
    application.add_handler(handler)

  job_queue = application.job_queue
  for plugin in plugins.values():
    if hasattr(plugin, "set_job_queue"):
      plugin.set_job_queue(job_queue)

  application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
  application.add_handler(MessageHandler(filters.PHOTO | filters.ANIMATION, handle_media))
  application.add_handler(CommandHandler("help", help_command))
  application.add_handler(CommandHandler("enable", lambda update, context: enable_plugin(update, context, config)))
  application.add_handler(CommandHandler("disable", disable_plugin))
  application.add_handler(CommandHandler("plugins", list_plugins))
  application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
  main()
