import time, os, logging

from aiogram            import Bot, Router, F, types
from aiogram.filters    import Command

from services.convert   import Converter
from database.repo      import DB_actions
from utils.decorators   import log

router  = Router()
db      = DB_actions()
logger  = logging.getLogger()

@router.message(Command("voice"))
async def toggle_voice_recognition(message: types.Message):
    chat_id = message.chat.id
    new_setting = db.toggle_voice_setting(chat_id)
    
    if new_setting:
        await message.reply("Voice recognition has been <b>disabled</b> for this chat.")
    else:
        await message.reply("Voice recognition has been <b>enabled</b> for this chat.")

@router.message(F.content_type.in_({'voice', 'video_note'}))
@log('SPEECH_REC')
async def get_audio_messages(message: types.Message, bot: Bot):
    if db.is_voice_disabled(message.chat.id):
        return
    
    file_name = None
    converter = None
    
    try:
        start_time = time.time()
        msg = await message.reply("<i>Recognizing ... </i>")

        file_id = (
            message.voice.file_id 
            if message.content_type in ['voice'] 
            else message.video_note.file_id
        )
        file_info = await bot.get_file(file_id)
        
        downloaded_file = await bot.download_file(file_info.file_path)
        file_name = str(message.message_id) + '.ogg'
        
        name = message.chat.first_name if message.chat.first_name else message.chat.title
        if not name:
            name = 'No_title'
        logger.info(f"Chat {name} (ID: {message.chat.id}) download file {file_name}")

        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file.getvalue())

        converter = Converter(file_name)
        recognized_text = converter.audio_to_text()

        end_time = time.time()
        taken_time = round(end_time - start_time, 2)

        message_text = f'<i>{recognized_text}</i>\n\n<code>{taken_time} sec</code>'
        await msg.edit_text(text=message_text)
        
    except Exception as e:
        logger.error(f'[audio_recognizer] Error: {e}')
        await msg.delete()
    finally:
        # Clean up resources
        if file_name and os.path.exists(file_name):
            os.remove(file_name)
        if converter:
            del converter