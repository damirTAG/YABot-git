from aiogram.fsm.state import State, StatesGroup

class GameStates(StatesGroup):
    waiting_for_choice = State()
    waiting_for_player = State()
    waiting_for_opponent_choice = State()

# class MusicState(StatesGroup):
#     track_uuid = State()

