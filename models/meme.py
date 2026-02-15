from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Meme:
    uuid: str
    title: str
    file_id: str
    type: str
    publisher_user_id: int
    id: Optional[int] = None
    is_verified: bool = False
    is_banned: bool = False
    review_message_id: Optional[int] = None
    review_chat_id: Optional[int] = None
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    # Optional field to hold tags when fetching full info
    tags: List[str] = field(default_factory=list) 

@dataclass
class MemeVote:
    meme_uuid: str
    user_id: int
    vote: int  # 1 or -1

@dataclass
class MemeUsage:
    meme_uuid: str
    user_id: int
    query_text: Optional[str] = None
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))