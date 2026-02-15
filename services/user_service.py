from database.db import DatabaseManager
from database.user_repository import UserRepository
from models.user import User
from typing import Optional

class UserService:
    def __init__(self, db_manager: DatabaseManager):
        self.user_repo = UserRepository(db_manager)

    # --- User Management ---
    async def register_user(self, user_id: int):
        await self.user_repo.upsert(user_id)

    async def get_user(self, user_id: int) -> Optional[User]:
        return await self.user_repo.get(user_id)
    
    async def get_all_user_ids(self) -> list[int]:
        return await self.user_repo.get_all_user_ids()

    async def set_ban(self, user_id: int, ban: bool = True):
        await self.user_repo.set_ban_status(user_id, ban)

    async def unban_all_users(self) -> int:
        return await self.user_repo.unban_all()
