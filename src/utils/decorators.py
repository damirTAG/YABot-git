
from functools          import wraps
from aiogram            import types
from database.repo    import DB_actions

db = DB_actions()

def log(command_name):
    def decorator(handler):
        @wraps(handler)
        async def wrapper(update, *args, **kwargs):
            user_id = None
            chat_id = None
            chat_type = None
            username = None
            first_name = None
            last_name = None

            if isinstance(update, types.Message): 
                    user_id = update.from_user.id
                    chat_id = update.chat.id
                    chat_type = update.chat.type
                    username = update.from_user.username
                    first_name = update.from_user.first_name
                    last_name = update.from_user.last_name
            elif isinstance(update, types.CallbackQuery): 
                    user_id = update.from_user.id
                    chat_id = update.message.chat.id if update.message else None
                    chat_type = update.message.chat.type if update.message else None
                    username = update.from_user.username
                    first_name = update.from_user.first_name
                    last_name = update.from_user.last_name
            elif isinstance(update, types.ChosenInlineResult):
                    user_id = update.from_user.id
                    username = update.from_user.username
                    first_name = update.from_user.first_name
                    last_name = update.from_user.last_name

            if user_id is None:
                    return await handler(update, *args, **kwargs)

            db.add_user(user_id, username, first_name, last_name)

            if chat_id and chat_type and chat_type != 'private':
                db.add_chat(chat_id)

            db.log_command(user_id, command_name)

            return await handler(update, *args, **kwargs)
        return wrapper
    return decorator