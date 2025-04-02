import logging, pytz, asyncio, json

from aiogram            import Bot, Router, F, types
from aiogram.filters    import Command, CommandObject
from datetime           import datetime

from database.repo      import DB_actions
from config.constants   import REFRESH_BUTTON as refresh, DAMIR_USER_ID, UPDATE_NOTIFY

router  = Router()
db      = DB_actions()
logger  = logging.getLogger()

@router.message(Command("admin"))
async def get_stats(message: types.Message):
    stats = db.get_stats()

    stats_text = (
        f"👥 Users: {stats['user_count']}\n"
        f"💬 Chats: {stats['chat_count']}\n"
        f"📂 Saved files: {stats['total_saved_files']}\n\n"
        
        f"<b>Top Commands:</b>\n"
    )
    
    for command, count in stats['top_commands']:
        stats_text += f"/{command}: {count}\n"
        
    stats_text += "\n👤 <b>TOP-10 last active users:</b>\n"
    for user in stats['recent_users']:
        username = f"@{user[0]}" if user[0] else f"{user[1] or ''} {user[2] or ''}".strip()
        last_used = user[3]
        last_used_utc = datetime.strptime(user[4], "%Y-%m-%d %H:%M:%S")  
        last_used_oral = last_used_utc.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")

        stats_text += f" - {username} (<code>/{last_used}</code>: {last_used_oral})\n"

    stats_text += "\n🔥 <b>TOP-10 most active:</b>\n"
    for user in stats['active_users']:
        username = f"@{user[0]}" if user[0] else f"{user[1] or ''} {user[2] or ''}".strip()
        command_count = user[3]
        stats_text += f" - {username}: {command_count} команд\n"

    stats_text += "\n💾 <b>TOP-10 users by saved files:</b>\n"
    for user in stats['top_savers']:
        username = f"@{user[0]}" if user[0] else f"{user[1] or ''} {user[2] or ''}".strip()
        file_count = user[3]
        stats_text += f" - {username}: {file_count} файлов\n"

    await message.reply(stats_text, reply_markup=refresh)

@router.message(Command("get"))
async def send_file(
    message: types.Message, command: CommandObject, bot: Bot
):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You are not authorized to use this command.")
    
    args = command.args
    
    if not args:
        await message.reply("Usage: /get {file_id}")
        return
    
    file_id = args.strip()
    
    try:
        await bot.send_document(chat_id=message.chat.id, document=file_id)
    except Exception as e:
        await message.reply(f"Failed to send file: {e}")


# user quality survey
VOTES_FILE = "votes.json"

def load_votes():
    try:
        with open(VOTES_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_votes(votes):
    try:
        with open(VOTES_FILE, "w") as file:
            json.dump(votes, file, indent=4)
    except Exception as e:
        print(f"Error saving votes: {e}")

votes = load_votes()

@router.message(Command('sendall'))
async def send_survey(m: types.Message, command: CommandObject, bot: Bot):
    if m.from_user.id == 1038468423:
        
        users = db.execute_query("SELECT user_id FROM users")
        pax = [row[0] for row in users]
        
        chats_list = db.execute_query("SELECT chat_Id FROM chats")
        chats = [row[0] for row in chats_list]
        
        print(f'Total {len(pax)} users and {len(chats)} chats')
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                (
                    types.InlineKeyboardButton("👍", callback_data="vote_up"),
                    types.InlineKeyboardButton("👎", callback_data="vote_down")
                )
            ]
        )
        
        total = 0
        args = command.args
        is_chat = args and args.lower() == 'chat'
        is_not_vote = args and args.lower() == 'rmvote'
        if is_chat:
            pax = chats
        
        for pax_id in pax:
            try:
                await bot.send_message(
                    pax_id, 
                    UPDATE_NOTIFY, 
                    reply_markup=None if is_not_vote else keyboard
                )
                total += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Failed to send message to {pax_id}: {e}")
        print(f"Messages sent: {total}")

@router.message(Command('results'))
async def show_results(m: types.Message):
    if m.from_user.id == 1038468423:
        votes_data = load_votes()
        yes_count = sum(1 for v in votes_data.values() if v == "Yes")
        no_count = sum(1 for v in votes_data.values() if v == "No")
        total_votes = len(votes_data)
        
        await m.reply(f"Results:\nYes: {yes_count}\nNo: {no_count}\nTotal voters: {total_votes}")

@router.callback_query(lambda c: c.data in ["vote_up", "vote_down"])
async def vote_handler(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    chat_id = str(callback_query.message.chat.id)
    vote = callback_query.data
    answer = 'Yes' if vote == 'vote_up' else 'No'
    
    if user_id in votes or chat_id in votes:
        await callback_query.answer("You've already voted", show_alert=True)
        return
    
    votes[user_id if callback_query.message.chat.type == 'private' else chat_id] = answer
    save_votes(votes)
    
    if callback_query.message.chat.type == 'private':
        await callback_query.message.edit_text(f"Thank you for your vote!\nYou voted: {answer}")
    else:
        yes_count = sum(1 for v in votes.values() if v == "Yes")
        no_count = sum(1 for v in votes.values() if v == "No")

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="👍", callback_data="vote_up"),
                    types.InlineKeyboardButton(text="👎", callback_data="vote_down")
                ]
            ]
        )

        await callback_query.message.edit_text(
            f"{UPDATE_NOTIFY}"
            f"\n\nYes: {yes_count}\nNo: {no_count}",
            reply_markup=keyboard
        )