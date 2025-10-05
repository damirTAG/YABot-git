import asyncio, json, pytz

from aiogram            import Bot, Router, F, types
from aiogram.filters    import Command, CommandObject
from aiogram.types      import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.repo      import DB_actions
from utils.helpers      import generate_stats_text, show_users_page
from config.constants   import ADMIN_KEYBOARD, DAMIR_USER_ID, UPDATE_NOTIFY

router  = Router()
db      = DB_actions()

class SearchStates(StatesGroup):
    waiting_for_search_term = State()

@router.message(Command("admin"))
async def get_stats(message: types.Message):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")
    
    stats       = db.get_stats()
    stats_text  = generate_stats_text(stats)

    search_button = InlineKeyboardButton(text="🔍 Search User", callback_data="search_user")
    
    extended_keyboard = []
    if hasattr(ADMIN_KEYBOARD, 'inline_keyboard'):
        extended_keyboard = ADMIN_KEYBOARD.inline_keyboard.copy()
    
    extended_keyboard.append([search_button])
    extended_admin_keyboard = InlineKeyboardMarkup(inline_keyboard=extended_keyboard)

    await message.reply(stats_text, reply_markup=extended_admin_keyboard)

@router.message(Command("users"))
async def view_users_command(message: types.Message):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")
    
    await show_users_page(message, page=0)

@router.message(Command("search"))
async def search_user_command(message: types.Message, command: CommandObject):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")
    
    if command.args:
        search_term = command.args.strip()
        await perform_user_search(message, search_term)
    else:
        await message.reply(
            "🔍 <b>Search Users</b>\n\n"
            "Please provide a search term:\n"
            "• User ID (e.g., 123456789)\n"
            "• Username (e.g., john_doe)\n"
            "• First/Last name\n\n"
            "Example: <code>/search 123456789</code>\n"
            "Example: <code>/search john_doe</code>"
        )

async def perform_user_search(message: types.Message, search_term: str, is_edit: bool = False):
    """Perform user search and display results."""
    if not search_term.strip():
        text = "❌ Please provide a valid search term."
        if is_edit:
            await message.edit_text(text)
        else:
            await message.reply(text)
        return
    
    users = db.search_users(search_term.strip())
    
    if not users:
        text = f"❌ No users found for: <code>{search_term}</code>"
        if is_edit:
            await message.edit_text(text)
        else:
            await message.reply(text)
        return
    
    search_text = f"🔍 <b>Search Results for:</b> <code>{search_term}</code>\n\n"
    search_text += f"Found {len(users)} user(s):\n\n"
    
    buttons = []
    for i, user in enumerate(users, 1):
        username_display = f"@{user['username']}" if user['username'] else "No username"
        name_display = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        if not name_display:
            name_display = "No name"

        joined_display = user['joined_at'].strftime("%Y-%m-%d")
        
        search_text += (
            f"{i}. ID: <code>{user['user_id']}</code>\n"
            f"   👤 {username_display}\n"
            f"   📝 {name_display}\n"
            f"   📅 {joined_display}\n\n"
        )
        
        if i <= 10:
            button_text = f"{i}. {username_display[:15]}"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"search_user_details:{user['user_id']}:{search_term}"
                )
            ])
    
    if len(users) > 10:
        search_text += f"... and {len(users) - 10} more users\n\n"
    
    # Add navigation buttons
    nav_buttons = [
        InlineKeyboardButton(text="🔍 New Search", callback_data="search_user"),
        InlineKeyboardButton(text="👥 All Users", callback_data="view_users:0")
    ]
    buttons.append(nav_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if is_edit:
        await message.edit_text(search_text, reply_markup=keyboard)
    else:
        await message.reply(search_text, reply_markup=keyboard)

# Callback handlers
@router.callback_query(F.data == "refresh_admin")
async def refresh_stats(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    stats       = db.get_stats()
    stats_text  = generate_stats_text(stats)

    search_button = InlineKeyboardButton(text="🔍 Search User", callback_data="search_user")
    
    extended_keyboard = []
    if hasattr(ADMIN_KEYBOARD, 'inline_keyboard'):
        extended_keyboard = ADMIN_KEYBOARD.inline_keyboard.copy()
    
    extended_keyboard.append([search_button])
    extended_admin_keyboard = InlineKeyboardMarkup(inline_keyboard=extended_keyboard)

    await callback_query.message.edit_text(
        stats_text,
        reply_markup=extended_admin_keyboard
    )
    
    await callback_query.answer("Stats updated!")

@router.callback_query(F.data == "search_user")
async def search_user_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)
    
    await state.set_state(SearchStates.waiting_for_search_term)
    await state.update_data(message_to_edit=callback_query.message)
    
    cancel_button = InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_search")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])
    
    await callback_query.message.edit_text(
        "🔍 <b>Search Users</b>\n\n"
        "Send me the search term:\n"
        "• User ID (e.g., 123456789)\n"
        "• Username (e.g., john_doe)\n"
        "• First/Last name\n\n"
        "Just type and send your search term...",
        reply_markup=keyboard
    )
    
    await callback_query.answer()

@router.message(SearchStates.waiting_for_search_term)
async def process_search_term(message: types.Message, state: FSMContext):
    if message.from_user.id != DAMIR_USER_ID:
        return
    
    data = await state.get_data()
    original_message = data.get('message_to_edit')
    
    search_term = message.text.strip()
    
    try:
        await message.delete()
    except:
        pass
    
    if original_message:
        await perform_user_search(original_message, search_term, is_edit=True)
    
    await state.clear()

@router.callback_query(F.data == "cancel_search")
async def cancel_search(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)
    
    await state.clear()
    
    stats = db.get_stats()
    stats_text = generate_stats_text(stats)
    
    search_button = InlineKeyboardButton(text="🔍 Search User", callback_data="search_user")
    extended_keyboard = []
    if hasattr(ADMIN_KEYBOARD, 'inline_keyboard'):
        extended_keyboard = ADMIN_KEYBOARD.inline_keyboard.copy()
    
    extended_keyboard.append([search_button])
    extended_admin_keyboard = InlineKeyboardMarkup(inline_keyboard=extended_keyboard)
    
    await callback_query.message.edit_text(stats_text, reply_markup=extended_admin_keyboard)
    await callback_query.answer("Search cancelled")

@router.callback_query(F.data.startswith("search_user_details:"))
async def search_user_details_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    parts = callback_query.data.split(':')
    user_id = int(parts[1])
    search_term = parts[2] if len(parts) > 2 else ""

    user_details = db.get_user_details(user_id)
    if not user_details:
        await callback_query.answer("User not found.", show_alert=True)
        return

    if search_term:
        await state.update_data(last_search_term=search_term)
    
    joined_at = user_details['joined_at']
    joined_at_oral = (
        joined_at.replace(tzinfo=pytz.utc)
        .astimezone(pytz.timezone('Etc/GMT-5'))
        .strftime("%Y-%m-%d %H:%M:%S")
    )
    
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
        cmd_time_oral = cmd['used_at'].replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")
        details_text += f"/{cmd['command']} - {cmd_time_oral}\n"
    
    # Back to search results or users list
    buttons = []
    if search_term:
        back_button = InlineKeyboardButton(
            text="« Back to Search", 
            callback_data="back_to_search_results"
        )
    else:
        back_button = InlineKeyboardButton(text="« Back to Users", callback_data="view_users:0")
    
    buttons.append([back_button])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback_query.message.edit_text(details_text, reply_markup=keyboard)
    await callback_query.answer()

@router.callback_query(F.data == "back_to_search_results")
async def back_to_search_results(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    data = await state.get_data()
    search_term = data.get("last_search_term")

    if search_term:
        await perform_user_search(callback_query.message, search_term, is_edit=True)
    else:
        await callback_query.message.edit_text(
            "🔍 Please use /search command or click 'Search User' button to perform a new search.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 New Search", callback_data="search_user")],
                [InlineKeyboardButton(text="📊 Admin Panel", callback_data="refresh_admin")]
            ])
        )
    await callback_query.answer()

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
    
    joined_at_oral = user_details['joined_at'].replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")
    
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
        cmd_time_oral = cmd['used_at'].replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")
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
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍", callback_data="vote_up"),
                    InlineKeyboardButton(text="👎", callback_data="vote_down")
                ]
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