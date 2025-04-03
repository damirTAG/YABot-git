import logging, asyncio, json, pytz

from aiogram            import Bot, Router, F, types
from aiogram.filters    import Command, CommandObject

from datetime           import datetime

from database.repo      import DB_actions
from utils.helpers      import generate_stats_text, show_users_page
from config.constants   import ADMIN_KEYBOARD, DAMIR_USER_ID, UPDATE_NOTIFY

router  = Router()
db      = DB_actions()
logger  = logging.getLogger()

@router.message(Command("admin"))
async def get_stats(message: types.Message):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")
    
    stats       = db.get_stats()
    stats_text  = generate_stats_text(stats)

    await message.reply(stats_text, reply_markup=ADMIN_KEYBOARD)

@router.message(Command("users"))
async def view_users_command(message: types.Message):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")
    
    await show_users_page(message, page=0)

# Callback handlers
@router.callback_query(F.data == "refresh_admin")
async def refresh_stats(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    stats       = db.get_stats()
    stats_text  = generate_stats_text(stats)

    await callback_query.message.delete()

    await callback_query.message.answer(
        stats_text,
        reply_markup=ADMIN_KEYBOARD
    )
    
    await callback_query.answer("Stats updated!")

@router.callback_query(F.data.startswith("view_users:"))
async def users_pagination_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)
    
    page = int(callback_query.data.split(':')[1])
    await show_users_page(callback_query.message, page, is_edit=True)
    await callback_query.answer()

@router.callback_query(F.data.startswith("user_details:"))
async def user_details_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)
    
    user_id = int(callback_query.data.split(':')[1])
    page = int(callback_query.data.split(':')[2])
    
    user_details = db.get_user_details(user_id)
    
    if not user_details:
        await callback_query.answer("User not found.", show_alert=True)
        return
    
    joined_at       = datetime.strptime(user_details['joined_at'], "%Y-%m-%d %H:%M:%S")
    joined_at_oral  = joined_at.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")
    
    details_text = (
        f"👤 <b>User Details</b>\n\n"
        f"ID: <code>{user_details['user_id']}</code>\n"
        f"Username: {('@' + user_details['username']) if user_details['username'] else 'Not set'}\n"
        f"Name: {user_details['first_name'] or ''} {user_details['last_name'] or ''}\n"
        f"Joined: {joined_at_oral}\n\n"
        f"Commands used: {user_details['command_count']}\n"
        f"Files saved: {user_details['saved_files']}\n\n"
        f"<b>Last 5 commands:</b>\n"
    )
    
    for cmd in user_details['recent_commands']:
        cmd_time = datetime.strptime(cmd['used_at'], "%Y-%m-%d %H:%M:%S")
        cmd_time_oral = cmd_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")
        details_text += f"/{cmd['command']} - {cmd_time_oral}\n"
    
    back_button = types.InlineKeyboardButton(text="« Back to Users", callback_data=f"view_users:{page}")
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    
    await callback_query.message.edit_text(details_text, reply_markup=keyboard)
    await callback_query.answer()

@router.message(Command("get"))
async def send_file(
    message: types.Message, command: CommandObject, bot: Bot
):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")
    
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