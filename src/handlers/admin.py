import asyncio

import pytz
from aiogram import Bot, F, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config.constants import ADMIN_KEYBOARD, DAMIR_USER_ID, UPDATE_NOTIFY
from database.repo import DB_actions
from utils.broadcast import BroadcastManager
from utils.helpers import generate_stats_text, show_users_page

router = Router()
db = DB_actions()


class SearchStates(StatesGroup):
    waiting_for_search_term = State()


@router.message(Command("admin"))
async def get_stats(message: types.Message):
    if message.from_user.id != DAMIR_USER_ID:
        return await message.reply("🚫 You can't use this command.")

    stats = db.get_stats()
    stats_text = generate_stats_text(stats)

    search_button = InlineKeyboardButton(text="🔍 Search User", callback_data="search_user")

    extended_keyboard = []
    if hasattr(ADMIN_KEYBOARD, "inline_keyboard"):
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
        username_display = f"@{user['username']}" if user["username"] else "No username"
        name_display = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        if not name_display:
            name_display = "No name"

        joined_display = user["joined_at"].strftime("%Y-%m-%d")

        search_text += (
            f"{i}. ID: <code>{user['user_id']}</code>\n"
            f"   👤 {username_display}\n"
            f"   📝 {name_display}\n"
            f"   📅 {joined_display}\n\n"
        )

        if i <= 10:
            button_text = f"{i}. {username_display[:15]}"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"search_user_details:{user['user_id']}:{search_term}",
                    )
                ]
            )

    if len(users) > 10:
        search_text += f"... and {len(users) - 10} more users\n\n"

    # Add navigation buttons
    nav_buttons = [
        InlineKeyboardButton(text="🔍 New Search", callback_data="search_user"),
        InlineKeyboardButton(text="👥 All Users", callback_data="view_users:0"),
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

    stats = db.get_stats()
    stats_text = generate_stats_text(stats)

    search_button = InlineKeyboardButton(text="🔍 Search User", callback_data="search_user")

    extended_keyboard = []
    if hasattr(ADMIN_KEYBOARD, "inline_keyboard"):
        extended_keyboard = ADMIN_KEYBOARD.inline_keyboard.copy()

    extended_keyboard.append([search_button])
    extended_admin_keyboard = InlineKeyboardMarkup(inline_keyboard=extended_keyboard)

    await callback_query.message.edit_text(stats_text, reply_markup=extended_admin_keyboard)

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
        reply_markup=keyboard,
    )

    await callback_query.answer()


@router.message(SearchStates.waiting_for_search_term)
async def process_search_term(message: types.Message, state: FSMContext):
    if message.from_user.id != DAMIR_USER_ID:
        return

    data = await state.get_data()
    original_message = data.get("message_to_edit")

    search_term = message.text.strip()

    try:
        await message.delete()
    except Exception:
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
    if hasattr(ADMIN_KEYBOARD, "inline_keyboard"):
        extended_keyboard = ADMIN_KEYBOARD.inline_keyboard.copy()

    extended_keyboard.append([search_button])
    extended_admin_keyboard = InlineKeyboardMarkup(inline_keyboard=extended_keyboard)

    await callback_query.message.edit_text(stats_text, reply_markup=extended_admin_keyboard)
    await callback_query.answer("Search cancelled")


@router.callback_query(F.data.startswith("search_user_details:"))
async def search_user_details_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    parts = callback_query.data.split(":")
    user_id = int(parts[1])
    search_term = parts[2] if len(parts) > 2 else ""

    user_details = db.get_user_details(user_id)
    if not user_details:
        await callback_query.answer("User not found.", show_alert=True)
        return

    if search_term:
        await state.update_data(last_search_term=search_term)

    joined_at = user_details["joined_at"]
    joined_at_oral = (
        joined_at.replace(tzinfo=pytz.utc)
        .astimezone(pytz.timezone("Etc/GMT-5"))
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

    for cmd in user_details["recent_commands"]:
        cmd_time_oral = (
            cmd["used_at"]
            .replace(tzinfo=pytz.utc)
            .astimezone(pytz.timezone("Etc/GMT-5"))
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        details_text += f"/{cmd['command']} - {cmd_time_oral}\n"

    # Back to search results or users list
    buttons = []
    if search_term:
        back_button = InlineKeyboardButton(
            text="« Back to Search", callback_data="back_to_search_results"
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
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 New Search", callback_data="search_user")],
                    [InlineKeyboardButton(text="📊 Admin Panel", callback_data="refresh_admin")],
                ]
            ),
        )
    await callback_query.answer()


@router.callback_query(F.data.startswith("view_users:"))
async def users_pagination_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    page = int(callback_query.data.split(":")[1])
    await show_users_page(callback_query.message, page, is_edit=True)
    await callback_query.answer()


@router.callback_query(F.data.startswith("user_details:"))
async def user_details_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DAMIR_USER_ID:
        return await callback_query.answer("🚫 You can't use this feature.", show_alert=True)

    user_id = int(callback_query.data.split(":")[1])
    page = int(callback_query.data.split(":")[2])

    user_details = db.get_user_details(user_id)

    if not user_details:
        await callback_query.answer("User not found.", show_alert=True)
        return

    joined_at_oral = (
        user_details["joined_at"]
        .replace(tzinfo=pytz.utc)
        .astimezone(pytz.timezone("Etc/GMT-5"))
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

    for cmd in user_details["recent_commands"]:
        cmd_time_oral = (
            cmd["used_at"]
            .replace(tzinfo=pytz.utc)
            .astimezone(pytz.timezone("Etc/GMT-5"))
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        details_text += f"/{cmd['command']} - {cmd_time_oral}\n"

    back_button = types.InlineKeyboardButton(
        text="« Back to Users", callback_data=f"view_users:{page}"
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])

    await callback_query.message.edit_text(details_text, reply_markup=keyboard)
    await callback_query.answer()


@router.message(Command("get"))
async def send_file(message: types.Message, command: CommandObject, bot: Bot):
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
broadcast_manager = BroadcastManager()
MAX_RETRIES = 3
BASE_DELAY = 0.05
BATCH_SIZE = 50


async def send_with_retry(
    bot: Bot,
    user_id: int,
    message: str,
    keyboard: InlineKeyboardMarkup | None = None,
    retries: int = MAX_RETRIES,
) -> dict:
    """Send message with retry logic and error categorization"""
    for attempt in range(retries):
        try:
            await bot.send_message(user_id, message, reply_markup=keyboard)
            return {"status": "sent", "error": None}
        except Exception as e:
            error_msg = str(e).lower()

            # Categorize errors
            if "blocked" in error_msg or "bot was blocked" in error_msg:
                return {"status": "blocked", "error": "User blocked the bot"}
            elif "chat not found" in error_msg or "user not found" in error_msg:
                return {"status": "not_found", "error": "User/chat not found"}
            elif "too many requests" in error_msg or "retry after" in error_msg:
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                return {"status": "rate_limited", "error": "Rate limit exceeded"}
            elif attempt < retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                return {"status": "failed", "error": str(e)}

    return {"status": "failed", "error": "Max retries exceeded"}


@router.message(Command("sendall"))
async def send_broadcast(m: types.Message, command: CommandObject, bot: Bot):
    """
    Send broadcast to all users/chats
    Usage:
        /sendall - Send with voting buttons
        /sendall rmvote - Send without voting buttons
        /sendall chat - Send to chats only
        /sendall preview - Preview message without sending
    """
    if m.from_user.id != 1038468423:
        return

    args = command.args
    is_chat = args and "chat" in args.lower()
    is_no_vote = args and "rmvote" in args.lower()
    is_preview = args and "preview" in args.lower()

    # Get message (you should replace UPDATE_NOTIFY with actual message)
    message_text = UPDATE_NOTIFY

    # Preview mode
    if is_preview:
        keyboard = (
            None
            if is_no_vote
            else InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="👍", callback_data="vote_up"),
                        InlineKeyboardButton(text="👎", callback_data="vote_down"),
                    ]
                ]
            )
        )
        await m.reply(f"Preview:\n\n{message_text}", reply_markup=keyboard)
        return

    # Get recipients
    if is_chat:
        chats_list = db.execute_query("SELECT chat_Id FROM chats")
        recipients = [row[0] for row in chats_list]
        recipient_type = "chats"
    else:
        users = db.execute_query("SELECT user_id FROM users")
        recipients = [row[0] for row in users]
        recipient_type = "users"

    if not recipients:
        await m.reply("No recipients found!")
        return

    # Create broadcast campaign
    broadcast_id = broadcast_manager.create_broadcast(message_text, not is_no_vote)

    # Prepare keyboard
    keyboard = (
        None
        if is_no_vote
        else InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍", callback_data=f"vote_up:{broadcast_id}"),
                    InlineKeyboardButton(text="👎", callback_data=f"vote_down:{broadcast_id}"),
                ]
            ]
        )
    )

    # Progress message
    progress_msg = await m.reply(
        f"🚀 Starting broadcast to {len(recipients)} {recipient_type}...\n\n"
        f"Progress: 0/{len(recipients)}\n"
        f"✅ Sent: 0\n"
        f"❌ Failed: 0\n"
        f"🚫 Blocked: 0"
    )

    # Send to all recipients
    stats = {
        "total": len(recipients),
        "sent": 0,
        "failed": 0,
        "blocked": 0,
        "not_found": 0,
        "rate_limited": 0,
    }

    failed_ids = []

    for i, recipient_id in enumerate(recipients, 1):
        result = await send_with_retry(bot, recipient_id, message_text, keyboard)

        # Update stats
        if result["status"] == "sent":
            stats["sent"] += 1
        elif result["status"] == "blocked":
            stats["blocked"] += 1
            failed_ids.append((recipient_id, result["error"]))
        elif result["status"] == "not_found":
            stats["not_found"] += 1
            failed_ids.append((recipient_id, result["error"]))
        elif result["status"] == "rate_limited":
            stats["rate_limited"] += 1
            failed_ids.append((recipient_id, result["error"]))
        else:
            stats["failed"] += 1
            failed_ids.append((recipient_id, result["error"]))

        # Update progress every BATCH_SIZE messages
        if i % BATCH_SIZE == 0 or i == len(recipients):
            progress_text = (
                f"🚀 Broadcast Progress\n\n"
                f"Progress: {i}/{len(recipients)}\n"
                f"✅ Sent: {stats['sent']}\n"
                f"❌ Failed: {stats['failed']}\n"
                f"🚫 Blocked: {stats['blocked']}\n"
                f"👻 Not Found: {stats['not_found']}\n"
                f"⏱ Rate Limited: {stats['rate_limited']}"
            )
            try:
                await progress_msg.edit_text(progress_text)
            except Exception:
                pass

        await asyncio.sleep(BASE_DELAY)

    # Save final stats
    broadcast_manager.update_broadcast_stats(broadcast_id, stats)

    # Final report
    success_rate = (stats["sent"] / stats["total"] * 100) if stats["total"] > 0 else 0
    final_text = (
        f"✅ Broadcast Complete!\n\n"
        f"📊 Results:\n"
        f"Total: {stats['total']}\n"
        f"✅ Sent: {stats['sent']} ({success_rate:.1f}%)\n"
        f"❌ Failed: {stats['failed']}\n"
        f"🚫 Blocked: {stats['blocked']}\n"
        f"👻 Not Found: {stats['not_found']}\n"
        f"⏱ Rate Limited: {stats['rate_limited']}\n\n"
        f"Broadcast ID: {broadcast_id}"
    )

    if failed_ids:
        final_text += f"\n\nUse /failures {broadcast_id} to see failed IDs"

    await progress_msg.edit_text(final_text)


@router.message(Command("results"))
async def show_results(m: types.Message, command: CommandObject):
    """Show voting results for a broadcast. Usage: /results [broadcast_id]"""
    if m.from_user.id != 1038468423:
        return

    args = command.args

    if not args:
        # Show all broadcasts
        history = broadcast_manager.get_broadcast_history()
        if not history:
            await m.reply("No broadcasts found.")
            return

        text = "📊 Broadcast History:\n\n"
        for b in history[:10]:  # Show last 10
            text += (
                f"ID: {b['id']}\n"
                f"Created: {b['created_at'][:19]}\n"
                f"Sent: {b['stats']['sent']}/{b['stats']['total']}\n"
                f"Message: {b['message']}\n\n"
            )

        await m.reply(text)
        return

    # Show specific broadcast results
    broadcast_id = args
    vote_stats = broadcast_manager.get_vote_stats(broadcast_id)

    if vote_stats["total"] == 0:
        await m.reply(f"No votes yet for broadcast {broadcast_id}")
        return

    yes_pct = (vote_stats["yes"] / vote_stats["total"] * 100) if vote_stats["total"] > 0 else 0
    no_pct = (vote_stats["no"] / vote_stats["total"] * 100) if vote_stats["total"] > 0 else 0

    text = (
        f"📊 Voting Results for {broadcast_id}\n\n"
        f"👍 Yes: {vote_stats['yes']} ({yes_pct:.1f}%)\n"
        f"👎 No: {vote_stats['no']} ({no_pct:.1f}%)\n"
        f"Total Votes: {vote_stats['total']}"
    )

    await m.reply(text)


@router.callback_query(lambda c: c.data and c.data.startswith(("vote_up:", "vote_down:")))
async def vote_handler(callback_query: types.CallbackQuery):
    """Handle voting on broadcasts"""
    parts = callback_query.data.split(":")
    vote_type = parts[0]
    broadcast_id = parts[1] if len(parts) > 1 else "default"

    user_id = str(callback_query.from_user.id)
    chat_id = str(callback_query.message.chat.id)
    is_private = callback_query.message.chat.type == "private"

    vote = "Yes" if vote_type == "vote_up" else "No"
    identifier = user_id if is_private else chat_id

    # Try to add vote
    if not broadcast_manager.add_vote(broadcast_id, identifier, vote):
        await callback_query.answer("You've already voted!", show_alert=True)
        return

    await callback_query.answer(f"Vote recorded: {vote}")

    # Update message
    if is_private:
        await callback_query.message.edit_text(f"Thank you for your feedback!\n\nYour vote: {vote}")
    else:
        # Show live results in groups
        vote_stats = broadcast_manager.get_vote_stats(broadcast_id)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍", callback_data=f"vote_up:{broadcast_id}"),
                    InlineKeyboardButton(text="👎", callback_data=f"vote_down:{broadcast_id}"),
                ]
            ]
        )

        original_text = callback_query.message.text.split("\n\n")[0]
        await callback_query.message.edit_text(
            f"{original_text}\n\n👍 Yes: {vote_stats['yes']}\n👎 No: {vote_stats['no']}",
            reply_markup=keyboard,
        )


@router.message(Command("failures"))
async def show_failures(m: types.Message, command: CommandObject):
    """Show failed recipients for a broadcast. Usage: /failures [broadcast_id]"""
    if m.from_user.id != 1038468423:
        return

    await m.reply(
        "Failed recipients logging not yet implemented in this version.\nCheck console logs for error details."
    )


@router.message(Command("cleanvotes"))
async def clean_old_votes(m: types.Message):
    """Clean old vote data (keep last 5 broadcasts)"""
    if m.from_user.id != 1038468423:
        return

    broadcasts = list(broadcast_manager.data["broadcasts"].items())
    if len(broadcasts) <= 5:
        await m.reply("No old broadcasts to clean.")
        return

    # Sort by created_at and keep last 5
    sorted_broadcasts = sorted(broadcasts, key=lambda x: x[1]["created_at"], reverse=True)

    to_keep = {bid for bid, _ in sorted_broadcasts[:5]}

    # Remove old broadcasts
    broadcast_manager.data["broadcasts"] = {
        bid: b for bid, b in broadcast_manager.data["broadcasts"].items() if bid in to_keep
    }
    broadcast_manager.data["votes"] = {
        bid: v for bid, v in broadcast_manager.data["votes"].items() if bid in to_keep
    }

    broadcast_manager.save_data()
    removed = len(broadcasts) - 5
    await m.reply(f"✅ Cleaned {removed} old broadcast(s).")
