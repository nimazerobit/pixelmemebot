from database.db import DatabaseManager
from services.user_service import UserService
from services.meme_service import MemeService
from services.status_service import StatusService

DB_PATH = "bot.db"

db_manager = DatabaseManager(DB_PATH)

user_service = UserService(db_manager)
meme_service = MemeService(db_manager)
status_service = StatusService(db_manager)
