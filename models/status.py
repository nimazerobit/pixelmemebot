from dataclasses import dataclass

@dataclass
class BotStats:
    total_users: int
    banned_users: int
    today_users: int
    total_usage: int
    today_usage: int
    total_memes: int
    unverified_memes: int
    today_memes: int

@dataclass
class UserStats:
    total_memes: int
    unverified_memes: int
    today_memes: int
    total_usage: int
    today_usage: int