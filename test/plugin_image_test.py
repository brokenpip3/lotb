from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from telegram import Message
from telegram import PhotoSize

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

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.execute(mock_update, mock_context)
    mock_save_image.assert_called_once_with(mock_update.effective_chat.id, "IronMan", "file_id_ironman")
    mock_update.message.reply_text.assert_called_once_with("Image saved with name: IronMan")


@pytest.mark.asyncio
async def test_recall_image(mock_update, mock_context, image_plugin):
  mock_update.message.text = "IronMan.img"

  with patch("lotb.plugins.image.Plugin.get_image", return_value="file_id_ironman") as mock_get_image:
    await image_plugin.recall_image(mock_update, mock_context)
    mock_get_image.assert_called_once_with(mock_update.effective_chat.id, "IronMan")
    mock_context.bot.send_photo.assert_called_once_with(chat_id=mock_update.effective_chat.id, photo="file_id_ironman")
    mock_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_recall_image_not_found(mock_update, mock_context, image_plugin):
  mock_update.message.text = "Hulk.img"

  with patch("lotb.plugins.image.Plugin.get_image", return_value=None) as mock_get_image:
    await image_plugin.recall_image(mock_update, mock_context)
    mock_get_image.assert_called_once_with(mock_update.effective_chat.id, "Hulk")
    mock_update.message.reply_text.assert_called_once_with("No image found with name: Hulk")


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
async def test_list_images(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image"

  with patch("lotb.plugins.image.Plugin.get_image_names", return_value=["avvocato", "ahnonposso"]) as mock_get_names:
    await image_plugin.execute(mock_update, mock_context)
    mock_get_names.assert_called_once_with(mock_update.effective_chat.id)
    mock_update.message.reply_text.assert_called_once_with("Available images:\n- avvocato\n- ahnonposso")


@pytest.mark.asyncio
async def test_list_images_empty(mock_update, mock_context, image_plugin):
  mock_update.message.text = "/image"

  with patch("lotb.plugins.image.Plugin.get_image_names", return_value=[]) as mock_get_names:
    await image_plugin.execute(mock_update, mock_context)
    mock_get_names.assert_called_once_with(mock_update.effective_chat.id)
    mock_update.message.reply_text.assert_called_once_with(
      "No images saved yet, reply to an image with /image <name> to save one"
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
async def test_handle_photo_with_caption(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde-778899-hal9000")]

  with patch("lotb.plugins.image.Plugin.save_image") as mock_save_image:
    await image_plugin.handle_photo(mock_update, mock_context)
    mock_save_image.assert_called_once_with(996699, "sunrise", "abcde-778899-hal9000")
    mock_update.message.reply_text.assert_awaited_once_with("Image saved with name: sunrise")


@pytest.mark.asyncio
async def test_handle_photo_missing_name(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde-778899-hal9000")]

  await image_plugin.handle_photo(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once_with("Please provide a name for the image.")


@pytest.mark.asyncio
async def test_handle_photo_missing_photo(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = None

  await image_plugin.handle_photo(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once_with("No photo found in the message.")


@pytest.mark.asyncio
async def test_handle_photo_missing_chat_info(mock_update, mock_context, image_plugin):
  mock_update.message.caption = "/image sunrise"
  mock_update.message.photo = [MagicMock(spec=PhotoSize, file_id="abcde-778899-hal9000")]
  mock_update.effective_chat = None

  await image_plugin.handle_photo(mock_update, mock_context)
  mock_update.message.reply_text.assert_awaited_once_with("Chat information is unavailable.")

@pytest.mark.asyncio
async def test_get_image_names_with_results(image_plugin, mock_db):
     mock_cursor = mock_db.mock_cursor
     mock_cursor.fetchall.return_value = [("sunrise",), ("dawn",), ("sunset",)]
     image_plugin.db_cursor = mock_cursor

     names = image_plugin.get_image_names(996699)
     assert names == ["sunrise", "dawn", "sunset"]
     mock_cursor.execute.assert_called_once_with(
         "SELECT name FROM images WHERE chat_id = ?", (996699,)
     )

@pytest.mark.asyncio
async def test_get_image_names_empty(image_plugin, mock_db):
    mock_cursor = mock_db.mock_cursor
    mock_cursor.fetchall.return_value = []
    image_plugin.db_cursor = mock_cursor

    names = image_plugin.get_image_names(996699)
    assert names == []
    mock_cursor.execute.assert_called_once_with(
        "SELECT name FROM images WHERE chat_id = ?", (996699,)
    )

@pytest.mark.asyncio
async def test_get_image_names_no_cursor(image_plugin):
    image_plugin.db_cursor = None
    names = image_plugin.get_image_names(996699)
    assert names == []
