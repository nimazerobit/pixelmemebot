from database.db import DatabaseManager
from database.meme_repository import MemeRepository
from models.meme import Meme
from typing import Optional, List

class MemeService:
    def __init__(self, db_manager: DatabaseManager):
        self.meme_repo = MemeRepository(db_manager)
    # --- Meme Management ---
    async def add_meme(self, uuid: str, title: str, file_id: str, type_: str, publisher_id: int, tags: List[str] = None):
        new_meme = Meme(
            uuid=uuid, title=title, file_id=file_id, 
            type=type_, publisher_user_id=publisher_id
        )
        
        await self.meme_repo.create(new_meme)
        if tags:
            await self.meme_repo.add_tags(uuid, tags)
        
        return True

    async def get_meme_full_details(self, uuid: str) -> Optional[Meme]:
        meme = await self.meme_repo.get_by_uuid(uuid)
        if meme:
            meme.tags = await self.meme_repo.get_tags(uuid)
        return meme
    
    async def get_meme_by_file_id(self, file_id: str) -> Optional[Meme]:
        meme = await self.meme_repo.get_by_file_id(file_id)
        return meme
    
    async def meme_file_exists(self, file_id: str) -> bool:
        return True if await self.meme_repo.exists_by_file_id(file_id) else False
    
    async def update_title(self, uuid: str, new_title: str):
        await self.meme_repo.update_title(uuid, new_title)

    async def update_tags(self, uuid: str, tags: List[str]):
        await self.meme_repo.update_tags(uuid, tags)

    async def verify_meme(self, uuid: str, verified: bool = True):
        await self.meme_repo.update_verification(uuid, verified)

    async def set_ban(self, uuid: str, banned: bool = True):
        await self.meme_repo.update_ban_status(uuid, banned)

    async def get_all_unverified(self) -> List[Meme]:
        return await self.meme_repo.get_all_unverified()

    async def delete_meme(self, uuid: str) -> bool:
        return await self.meme_repo.delete(uuid)

    # --- Review Logic ---
    def set_review_message(self, uuid: str, chat_id: int, message_id: int):
        self.meme_repo.set_review_details(uuid, chat_id, message_id)

    # --- Voting & Usage ---
    async def vote_for_meme(self, uuid: str, user_id: int, vote: int):
        if vote not in (1, -1):
            raise ValueError("Vote must be 1 or -1")
        await self.meme_repo.upsert_vote(uuid, user_id, vote)

    async def get_vote_info(self, uuid: str, user_id: int):
        counts = await self.meme_repo.get_vote_stats(uuid)
        user_vote = await self.meme_repo.get_user_vote(uuid, user_id)
        return counts, user_vote

    async def search_memes_for_inline(self, user_id: int, query: str, limit: int = 50, offset: int = 0):
        # Pass the limit to the repository
        memes = await self.meme_repo.search_inline(user_id, query, limit=limit, offset=offset)

        if memes:
            uuids = [meme["uuid"] for meme in memes]
            tags_map = await self.meme_repo.get_tags_map(uuids)
            for meme in memes:
                meme["tags"] = tags_map.get(meme["uuid"], "")

        return memes

    async def record_usage(self, uuid: str, user_id: int, query: str):
        await self.meme_repo.log_usage(uuid, user_id, query)