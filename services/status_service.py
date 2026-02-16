from database.db import DatabaseManager
from database.status_repository import StatusRepository

class StatusService:
    def __init__(self, db_manager: DatabaseManager):
        self.status_repo = StatusRepository(db_manager)
    # --- Statistics ---
    async def get_dashboard_stats(self):
        return await self.status_repo.get_bot_stats()

    async def get_user_stats(self, user_id: int):
        return await self.status_repo.get_user_stats(user_id)
    
    async def get_top_publishers(self, limit: int = 10, timestamp: int = None):
        return await self.status_repo.get_top_publishers(limit, timestamp)
    
    async def get_publisher_rank(self, user_id: int, timestamp: int = None):
        return await self.status_repo.get_publisher_rank(user_id, timestamp)