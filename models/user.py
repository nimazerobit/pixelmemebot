from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    user_id: int
    banned: bool = False
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))