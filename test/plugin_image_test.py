from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
import pytest
from telegram import Animation
from telegram import Message
from telegram import PhotoSize
from telegram import Sticker

from lotb.common.config import Config
from lotb.plugins.image import Plugin


@pytest.fixture
def mock_config():
  config = MagicMock(spec=Config)
  config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.image": {"enabled": "true", "accesskey": "jamaica", "secretkey": "japan"},
  }.get(key, default)
  return config


@pytest.fixture
def image_plugin(mock_config):
  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()
  return plugin


@pytest.mark.asyncio
async def test_save_image(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image IronMan"
  mock_update.message.reply_to_message = MagicMock(spec=Message)
  mock_update.message.reply_to_message.photo = [MagicMock(spec=PhotoSize, file_id="file_id_ironman")]
  mock_update.message.reply_to_message.animation = None
  mock_update.message.reply_to_message.sticker = None

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.execute(mock_update, mock_context)
    mock_save_image.assert_called_once_with(mock_update.effective_chat.id, "IronMan", "file_id_ironman", "photo")
    mock_update.message.reply_text.assert_called_once_with("photo saved with name: IronMan")


@pytest.mark.asyncio
async def test_recall_image(mock_update, mock_context, image_plugin):
  mock_update.message.text = "IronMan.img"

  with patch("lotb.plugins.image.Plugin.get_image", return_value="file_id_ironman") as mock_get_image:
    await image_plugin.recall_image(mock_update, mock_context)
    mock_get_image.assert_called_once_with(mock_update.effective_chat.id, "IronMan", "photo")
    mock_context.bot.send_photo.assert_called_once_with(chat_id=mock_update.effective_chat.id, photo="file_id_ironman")


@pytest.mark.asyncio
async def test_recall_sticker(mock_update, mock_context, image_plugin):
  mock_update.message.text = "cool.stk"

  with patch("lotb.plugins.image.Plugin.get_image", return_value="file_id_sticker"):
    mock_context.bot.send_sticker = AsyncMock()
    await image_plugin.recall_image(mock_update, mock_context)

    mock_context.bot.send_sticker.assert_awaited_once_with(
      chat_id=mock_update.effective_chat.id, sticker="file_id_sticker"
    )


@pytest.mark.asyncio
async def test_recall_gif(mock_update, mock_context, image_plugin):
  mock_update.message.text = "DancingBanana.gif"

  with patch("lotb.plugins.image.Plugin.get_image", return_value="file_id_banana"):
    mock_context.bot.send_animation = AsyncMock()
    await image_plugin.recall_image(mock_update, mock_context)

    mock_context.bot.send_animation.assert_awaited_once_with(
      chat_id=mock_update.effective_chat.id, animation="file_id_banana"
    )


@pytest.mark.asyncio
async def test_recall_image_not_found(mock_update, mock_context, image_plugin):
  mock_update.message.text = "Hulk.img"

  with patch("lotb.plugins.image.Plugin.get_image", return_value=None) as mock_get_image:
    await image_plugin.recall_image(mock_update, mock_context)
    mock_get_image.assert_called_once_with(mock_update.effective_chat.id, "Hulk", "photo")
    mock_update.message.reply_text.assert_called_once_with("No photo found with name: Hulk")


@pytest.mark.asyncio
async def test_recall_sticker_not_found(mock_update, mock_context, image_plugin):
  mock_update.message.text = "missing.stk"

  with patch("lotb.plugins.image.Plugin.get_image", return_value=None) as mock_get_image:
    await image_plugin.recall_image(mock_update, mock_context)
    mock_get_image.assert_called_once_with(mock_update.effective_chat.id, "missing", "sticker")
    mock_update.message.reply_text.assert_called_once_with("No sticker found with name: missing")


@pytest.mark.asyncio
async def test_recall_gif_not_found(mock_update, mock_context, image_plugin):
  mock_update.message.text = "thisGifdoesNotExist.gif"

  with patch("lotb.plugins.image.Plugin.get_image", return_value=None) as mock_get_image:
    await image_plugin.recall_image(mock_update, mock_context)
    mock_get_image.assert_called_once_with(mock_update.effective_chat.id, "thisGifdoesNotExist", "gif")
    mock_update.message.reply_text.assert_called_once_with("No gif found with name: thisGifdoesNotExist")


@pytest.mark.asyncio
async def test_unsplash_search_success(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image sunset"

  with patch("lotb.plugins.image.httpx.AsyncClient.get") as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"urls": {"regular": "https://example.com/sunset_image.jpg"}}]
    mock_get.return_value = mock_response

    await image_plugin.execute(mock_update, mock_context)

    mock_get.assert_called_once_with(
      "https://api.unsplash.com/photos/random?query=sunset&client_id=jamaica&count=10",
      headers={"Authorization": "Client-ID jamaica", "Secret-Key": "japan"},
    )
    mock_context.bot.send_photo.assert_called_once_with(
      chat_id=mock_update.effective_chat.id, photo="https://example.com/sunset_image.jpg"
    )


@pytest.mark.asyncio
async def test_unsplash_search_no_results(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image unknownterm"

  with patch("lotb.plugins.image.httpx.AsyncClient.get") as mock_get:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    await image_plugin.execute(mock_update, mock_context)

    mock_get.assert_called_once_with(
      "https://api.unsplash.com/photos/random?query=unknownterm&client_id=jamaica&count=10",
      headers=image_plugin.unsplash_auth,
    )
    mock_update.message.reply_text.assert_called_once_with("No image found for term: unknownterm")


@pytest.mark.asyncio
async def test_list_images_grouped(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image"

  with patch(
    "lotb.plugins.image.Plugin.get_media_list",
    return_value=[("sunrise", "photo"), ("dancing", "gif"), ("cool", "sticker"), ("sunset", "photo"), ("funny", "gif")],
  ) as mock_get_media:
    await image_plugin.execute(mock_update, mock_context)
    mock_get_media.assert_called_once_with(mock_update.effective_chat.id)

    args, kwargs = mock_update.message.reply_text.call_args
    response = args[0]
    assert "📁 Saved media:" in response
    assert "📷 images:" in response
    assert "  • sunrise" in response
    assert "  • sunset" in response
    assert "🎬 gif:" in response
    assert "  • dancing" in response
    assert "  • funny" in response
    assert "🖼️ stickers:" in response
    assert "  • cool" in response
    assert response.find("📷 images") < response.find("🎬 gif") < response.find("🖼️ stickers")
    assert response.find("sunrise") < response.find("sunset")
    assert response.find("dancing") < response.find("funny")


@pytest.mark.asyncio
async def test_list_images_empty(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image"

  with patch("lotb.plugins.image.Plugin.get_media_list", return_value=[]) as mock_get_media:
    await image_plugin.execute(mock_update, mock_context)
    mock_get_media.assert_called_once_with(mock_update.effective_chat.id)
    mock_update.message.reply_text.assert_called_once_with(
      "No media saved yet, reply to an image with /image <name> to save one"
    )


@pytest.mark.asyncio
async def test_unsplash_search_api_error(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image sunset"
  mock_update.effective_chat.id = 996699

  with patch("lotb.plugins.image.httpx.AsyncClient.get") as mock_get:
    mock_get.return_value.status_code = 500
    mock_get.return_value.json = AsyncMock(return_value={})
    await image_plugin.execute(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("No image found for term: sunset")
    # TODO ^ fix me, it should return "error occurred while fetching image from unsplash"


@pytest.mark.asyncio
async def test_execute_missing_chat_info(mock_update, mock_context, image_plugin):
  mock_update.effective_chat = None
  await image_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Chat information is unavailable.")


@pytest.mark.asyncio
async def test_handle_media_with_caption(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde-778899-hal9000")]

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.handle_media(mock_update, mock_context)
    mock_save_image.assert_called_once_with(996699, "sunrise", "abcde-778899-hal9000", "photo")
    mock_update.message.reply_text.assert_awaited_once_with("Saved with name: sunrise")


@pytest.mark.asyncio
async def test_handle_sticker_with_caption(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image awesome"
  mock_update.message.sticker = MagicMock(spec=Sticker, file_id="sticker-98765")
  mock_update.message.animation = None
  mock_update.message.photo = None

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.handle_media(mock_update, mock_context)
    mock_save_image.assert_called_once_with(996699, "awesome", "sticker-98765", "sticker")
    mock_update.message.reply_text.assert_awaited_once_with("Saved with name: awesome")


@pytest.mark.asyncio
async def test_handle_gif_with_caption(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image dancing"
  mock_update.message.animation = MagicMock(spec=Animation, file_id="gif-789906")
  mock_update.message.photo = None

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.handle_media(mock_update, mock_context)
    mock_save_image.assert_called_once_with(996699, "dancing", "gif-789906", "gif")
    mock_update.message.reply_text.assert_awaited_once_with("Saved with name: dancing")


@pytest.mark.asyncio
async def test_handle_media_missing_name(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde-778899-hal9000")]

  await image_plugin.handle_media(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once_with("Please provide a name for the media.")


@pytest.mark.asyncio
async def test_handle_media_missing_media(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = None
  mock_update.message.animation = None
  mock_update.message.sticker = None

  await image_plugin.handle_media(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once_with("No media found in the message.")


@pytest.mark.asyncio
async def test_handle_media_missing_chat_info(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde-778899-hal9000")]
  mock_update.effective_chat = None

  await image_plugin.handle_media(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once_with("Chat information is unavailable.")


@pytest.mark.asyncio
async def test_unsplash_keys_not_provided(mock_config, caplog):
  mock_config.get.side_effect = lambda key, default=None: {
    "core.database": ":memory:",
    "plugins.image": {"enabled": "true"},
  }.get(key, default)

  plugin = Plugin()
  plugin.set_config(mock_config)
  plugin.initialize()

  assert plugin.unsplash_access_key is None
  assert plugin.unsplash_secret_key is None
  assert plugin.unsplash_auth is None
  assert "Unsplash access key and/or secret key not provided" in caplog.text


@pytest.mark.asyncio
async def test_execute_with_sticker_reply(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image lol"
  mock_update.message.reply_to_message = MagicMock(spec=Message)
  mock_update.message.reply_to_message.sticker = MagicMock(spec=Sticker, file_id="sticker_id")
  mock_update.message.reply_to_message.animation = None
  mock_update.message.reply_to_message.photo = None

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.execute(mock_update, mock_context)
    mock_save_image.assert_called_once_with(mock_update.effective_chat.id, "lol", "sticker_id", "sticker")


@pytest.mark.asyncio
async def test_execute_with_gif_reply(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image dancing"
  mock_update.message.reply_to_message = MagicMock(spec=Message)
  mock_update.message.reply_to_message.animation = MagicMock(spec=Animation, file_id="gif_id")
  mock_update.message.reply_to_message.sticker = None
  mock_update.message.reply_to_message.photo = None

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.execute(mock_update, mock_context)
    mock_save_image.assert_called_once_with(mock_update.effective_chat.id, "dancing", "gif_id", "gif")


@pytest.mark.asyncio
async def test_unsplash_search_error(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image error"

  with patch("lotb.plugins.image.httpx.AsyncClient.get") as mock_get:
    mock_get.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock(status_code=500))
    await image_plugin.execute(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once_with("error occurred while fetching image from unsplash")


@pytest.mark.asyncio
async def test_recall_image_no_message_text(mock_update, mock_context, image_plugin):
  mock_update.message.text = None
  await image_plugin.recall_image(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_once_with("Message text is unavailable.")


@pytest.mark.asyncio
async def test_recall_image_invalid_pattern(mock_update, mock_context, image_plugin):
  mock_update.message.text = "invalid.pattern"
  await image_plugin.recall_image(mock_update, mock_context)
  mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_name_error(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image IronMan"
  mock_update.message.reply_to_message = MagicMock(spec=Message)
  mock_update.message.reply_to_message.photo = [MagicMock(spec=PhotoSize, file_id="file_id_ironman")]
  mock_update.message.reply_to_message.animation = None
  mock_update.message.reply_to_message.sticker = None

  await image_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_with("photo saved with name: IronMan")

  mock_update.message.reply_text.reset_mock()
  await image_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_with("A photo named 'IronMan' already exists, use a different name.")


@pytest.mark.asyncio
async def test_handle_media_duplicate_name(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde")]
  await image_plugin.handle_media(mock_update, mock_context)

  mock_update.message.reply_text.reset_mock()
  await image_plugin.handle_media(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_with("A photo named 'sunrise' already exists, use a different name.")


@pytest.mark.asyncio
async def test_different_types_same_name(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image cat"
  mock_update.message.reply_to_message = MagicMock(spec=Message)
  mock_update.message.reply_to_message.photo = [MagicMock(spec=PhotoSize, file_id="photo_cat")]
  mock_update.message.reply_to_message.animation = None
  mock_update.message.reply_to_message.sticker = None
  await image_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_with("photo saved with name: cat")

  mock_update.message.reply_text.reset_mock()
  mock_update.message.text = "/image cat"
  mock_update.message.reply_to_message.photo = None
  mock_update.message.reply_to_message.animation = MagicMock(spec=Animation, file_id="gif_cat")
  mock_update.message.reply_to_message.sticker = None
  await image_plugin.execute(mock_update, mock_context)
  mock_update.message.reply_text.assert_called_with("gif saved with name: cat")


@pytest.mark.asyncio
async def test_unsplash_search_random_image(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image random"

  with (
    patch("lotb.plugins.image.httpx.AsyncClient.get") as mock_get,
    patch("lotb.plugins.image.random.choice") as mock_choice,
  ):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["this-is-a-image", "this-is-another-image"]
    mock_get.return_value = mock_response
    mock_choice.return_value = {"urls": {"regular": "random_image.jpg"}}

    await image_plugin.execute(mock_update, mock_context)
    mock_choice.assert_called_once_with(["this-is-a-image", "this-is-another-image"])
    mock_context.bot.send_photo.assert_called_once_with(chat_id=mock_update.effective_chat.id, photo="random_image.jpg")


@pytest.mark.asyncio
async def test_execute_search_no_reply(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image term"
  mock_update.message.reply_to_message = None

  with patch("lotb.plugins.image.Plugin.search_unsplash_image", return_value="https://example.com/image.jpg"):
    await image_plugin.execute(mock_update, mock_context)
    mock_context.bot.send_photo.assert_called_once()


@pytest.mark.asyncio
async def test_get_media_list_with_results(image_plugin, mock_db):
  mock_cursor = mock_db.mock_cursor
  mock_cursor.fetchall.return_value = [("sunrise", "photo"), ("dawn", "photo"), ("sunset", "photo")]
  image_plugin.db_cursor = mock_cursor

  names = image_plugin.get_media_list(996699)
  assert names == [("sunrise", "photo"), ("dawn", "photo"), ("sunset", "photo")]
  mock_cursor.execute.assert_called_once_with("SELECT name, file_type FROM images WHERE chat_id = ?", (996699,))


@pytest.mark.asyncio
async def test_get_media_list_empty(image_plugin, mock_db):
  mock_cursor = mock_db.mock_cursor
  mock_cursor.fetchall.return_value = []
  image_plugin.db_cursor = mock_cursor

  names = image_plugin.get_media_list(996699)
  assert names == []
  mock_cursor.execute.assert_called_once_with("SELECT name, file_type FROM images WHERE chat_id = ?", (996699,))


@pytest.mark.asyncio
async def test_get_media_list_no_cursor(image_plugin):
  image_plugin.db_cursor = None
  names = image_plugin.get_media_list(996699)
  assert names == []
