import pytz

from datetime           import datetime
from aiogram            import types
from config             import constants
from database.repo      import DB_actions

db = DB_actions()

async def show_users_page(message: types.Message, page=0, is_edit=False):
    users = db.get_all_users(limit=constants.ADMIN_USERS_PER_PAGE, offset=page * constants.ADMIN_USERS_PER_PAGE)
    total_users = db.get_total_users_count()
    total_pages = (total_users + constants.ADMIN_USERS_PER_PAGE - 1) // constants.ADMIN_USERS_PER_PAGE
        
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
        
    text = f"👥 <b>Users List</b> (Page {page + 1} of {total_pages})\n\n"
        
    for user in users:
        username = f"@{user['username']}" if user['username'] else f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        if not username:
            username = f"User {user['user_id']}"
        text += f"• {username} - ID: <code>{user['user_id']}</code>\n"

    keyboard = []

    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton(text="« Prev", callback_data=f"view_users:{page-1}"))
        
    nav_row.append(types.InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        
    if page < total_pages - 1:
        nav_row.append(types.InlineKeyboardButton(text="Next »", callback_data=f"view_users:{page+1}"))
        
    keyboard.append(nav_row)

    for user in users:
        user_id = user['user_id']
        username = f"@{user['username']}" if user['username'] else f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        if not username:
            username = f"User {user_id}"
            
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"👤 {username[:20]}", 
                callback_data=f"user_details:{user_id}:{page}"
            )
        ])

    keyboard.append([types.InlineKeyboardButton(text="🔙 Back to Admin", callback_data="refresh_admin")])
        
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        
    if is_edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply(text, reply_markup=markup)

def generate_stats_text(stats):
    stats_text = (
            f"👥 Users: <code>{stats['user_count']}</code>\n"
            f"💬 Chats: <code>{stats['chat_count']}</code>\n"
            f"📂 Saved files: <code>{stats['total_saved_files']}</code>\n\n"
            f"<b>Top Commands:</b>\n"
    )
        
    for command, count in stats['top_commands']:
        stats_text += f"/{command}: {count}\n"
            
    stats_text += "\n👤 <b>10 last active users:</b>\n"
    for user in stats['recent_users']:
        username = f"@{user[0]}" if user[0] else f"{user[1] or ''} {user[2] or ''}".strip()
        last_used = user[3]
        last_used_utc = datetime.strptime(user[4], "%Y-%m-%d %H:%M:%S")
        last_used_oral = last_used_utc.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Etc/GMT-5')).strftime("%Y-%m-%d %H:%M:%S")
        stats_text += f" - {username} (<code>/{last_used}</code>: {last_used_oral})\n"
        
    stats_text += "\n🔥 <b>10 most active:</b>\n"
    for user in stats['active_users']:
        username = f"@{user[0]}" if user[0] else f"{user[1] or ''} {user[2] or ''}".strip()
        command_count = user[3]
        stats_text += f" - {username}: {command_count} command\n"
            
    stats_text += "\n💾 <b>10 users by saved files:</b>\n"
    for user in stats['top_savers']:
        username = f"@{user[0]}" if user[0] else f"{user[1] or ''} {user[2] or ''}".strip()
        file_count = user[3]
        stats_text += f" - {username}: <code>{file_count}</code> files\n"
            
    return stats_text