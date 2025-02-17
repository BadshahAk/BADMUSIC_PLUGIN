from inspect import getfullargspec
from re import findall
import datetime

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import BANNED_USERS
from BADMUSIC import app
from BADMUSIC.utils.database import (
    delete_note,
    deleteall_notes,
    get_note,
    get_note_names,
    save_note,
)
from utils.error import capture_err
from BADMUSIC.utils.functions import (
    check_format,
    extract_text_and_keyb,
    get_data_and_name,
)
from BADMUSIC.utils.keyboard import ikb
from utils.permissions import adminsOnly, member_permissions

private_notes_enabled = {}

async def eor(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user and msg.from_user.is_self else msg.reply
    return await func(**kwargs)

@app.on_message(filters.command("privatenotes") & filters.group & ~BANNED_USERS)
@adminsOnly("can_change_info")
async def toggle_private_notes(_, message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        return await eor(message, text="**Usage:** /privatenotes [on|off]")
    
    action = message.command[1].lower()
    if action == "on":
        private_notes_enabled[chat_id] = True
        await eor(message, text="✅ Private notes have been enabled.")
    elif action == "off":
        private_notes_enabled[chat_id] = False
        await eor(message, text="❌ Private notes have been disabled.")
    else:
        await eor(message, text="**Usage:** /privatenotes [on|off]")

@app.on_message(filters.command("save") & filters.group & ~BANNED_USERS)
@adminsOnly("can_change_info")
async def save_notee(_, message):
    if len(message.command) < 2:
        return await eor(
            message, text="**Usage:**\nReply to a message with /save [NOTE_NAME] to save a new note."
        )

    replied_message = message.reply_to_message
    if not replied_message:
        return await eor(message, text="You need to reply to a message to save it.")

    data, name = await get_data_and_name(replied_message, message)
    if data == "error":
        return await eor(message, text="Invalid format. Try again.")

    _type = None
    file_id = None
    if replied_message.text:
        _type = "text"
    elif replied_message.sticker:
        _type = "sticker"
        file_id = replied_message.sticker.file_id
    elif replied_message.photo:
        _type = "photo"
        file_id = replied_message.photo.file_id
    elif replied_message.document:
        _type = "document"
        file_id = replied_message.document.file_id
    elif replied_message.video:
        _type = "video"
        file_id = replied_message.video.file_id
    elif replied_message.audio:
        _type = "audio"
        file_id = replied_message.audio.file_id
    elif replied_message.voice:
        _type = "voice"
        file_id = replied_message.voice.file_id

    if replied_message.reply_markup:
        buttons = extract_text_and_keyb(ikb, data)
        if buttons:
            data, keyb = buttons
            note = {"type": _type, "data": data, "file_id": file_id, "keyboard": keyb}
        else:
            note = {"type": _type, "data": data, "file_id": file_id}
    else:
        note = {"type": _type, "data": data, "file_id": file_id}

    chat_id = message.chat.id
    await save_note(chat_id, name, note)
    await eor(message, text=f"✅ Note **{name}** saved successfully.")

@app.on_message(filters.command("notes") & filters.group & ~BANNED_USERS)
@capture_err
async def get_notes(_, message):
    chat_id = message.chat.id
    _notes = await get_note_names(chat_id)

    if not _notes:
        return await eor(message, text="❌ No notes found in this chat.")
    
    msg = "**📜 List of saved notes:**\n"
    for note in _notes:
        msg += f"🔹 `{note}`\n"
    
    await eor(message, text=msg)

@app.on_message(filters.command("get") & filters.group & ~BANNED_USERS)
@capture_err
async def get_one_note(_, message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        return await eor(message, text="**Usage:** /get [NOTE_NAME]")

    name = message.command[1]
    _note = await get_note(chat_id, name)
    if not _note:
        return await eor(message, text="❌ Note not found.")

    type_ = _note["type"]
    data = _note["data"]
    file_id = _note.get("file_id")
    keyb = _note.get("keyboard")

    if private_notes_enabled.get(chat_id, False):
        await message.reply_text(
            text="🔒 Private notes are enabled. Click the button below to view in PM.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Click here", url=f"https://t.me/{app.username}?start={name}")]]
            ),
        )
    else:
        await get_reply(message, type_, file_id, data, keyb)

async def get_reply(message, type_, file_id, data, keyb):
    if type_ == "text":
        await message.reply_text(text=data, reply_markup=keyb, disable_web_page_preview=True)
    elif type_ == "sticker":
        await message.reply_sticker(sticker=file_id)
    elif type_ == "photo":
        await message.reply_photo(photo=file_id, caption=data, reply_markup=keyb)
    elif type_ == "document":
        await message.reply_document(document=file_id, caption=data, reply_markup=keyb)
    elif type_ == "video":
        await message.reply_video(video=file_id, caption=data, reply_markup=keyb)
    elif type_ == "audio":
        await message.reply_audio(audio=file_id, caption=data, reply_markup=keyb)
    elif type_ == "voice":
        await message.reply_voice(voice=file_id, caption=data, reply_markup=keyb)

@app.on_message(filters.command("delete") & filters.group & ~BANNED_USERS)
@adminsOnly("can_change_info")
async def del_note(_, message):
    if len(message.command) < 2:
        return await eor(message, text="**Usage:** /delete [NOTE_NAME]")

    name = message.command[1].strip()
    chat_id = message.chat.id
    deleted = await delete_note(chat_id, name)

    if deleted:
        await eor(message, text=f"✅ Note **{name}** deleted successfully.")
    else:
        await eor(message, text="❌ No such note found.")

@app.on_message(filters.command("deleteall") & filters.group & ~BANNED_USERS)
@adminsOnly("can_change_info")
async def delete_all(_, message):
    chat_id = message.chat.id
    _notes = await get_note_names(chat_id)

    if not _notes:
        return await eor(message, text="❌ No notes found in this chat.")
    
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes, delete all", callback_data="delete_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data="delete_no"),
            ]
        ]
    )
    await message.reply_text(
        "**⚠ Are you sure you want to delete all saved notes?**",
        reply_markup=keyboard,
    )

@app.on_callback_query(filters.regex("delete_(.*)"))
async def delete_all_cb(_, cb):
    chat_id = cb.message.chat.id
    action = cb.data.split("_", 1)[1]
    if action == "yes":
        await deleteall_notes(chat_id)
        await cb.message.edit("✅ All notes deleted successfully.")
    else:
        await cb.message.delete()
