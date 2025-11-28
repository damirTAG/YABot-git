import json
import time
from datetime import datetime
from typing import Dict, List

VOTES_DB_FILE = "broadcast_data.json"
MAX_RETRIES = 3
BASE_DELAY = 0.05  # 50ms between messages (20 msg/sec)
BATCH_SIZE = 50  # Update progress every 50 messages


class BroadcastManager:
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        """Load all broadcast data from file"""
        try:
            with open(VOTES_DB_FILE, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "broadcasts": {},
                "votes": {},
                "stats": {}
            }
    
    def save_data(self):
        """Save all data to file"""
        try:
            with open(VOTES_DB_FILE, "w") as file:
                json.dump(self.data, file, indent=4)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def create_broadcast(self, message: str, include_vote: bool = True) -> str:
        """Create a new broadcast campaign"""
        broadcast_id = str(int(time.time()))
        self.data["broadcasts"][broadcast_id] = {
            "message": message,
            "include_vote": include_vote,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "stats": {
                "total": 0,
                "sent": 0,
                "failed": 0,
                "blocked": 0,
                "not_found": 0,
                "rate_limited": 0
            }
        }
        self.data["votes"][broadcast_id] = {}
        self.save_data()
        return broadcast_id
    
    def add_vote(self, broadcast_id: str, user_id: str, vote: str) -> bool:
        """Add a vote for a broadcast. Returns False if already voted"""
        if broadcast_id not in self.data["votes"]:
            self.data["votes"][broadcast_id] = {}
        
        if user_id in self.data["votes"][broadcast_id]:
            return False
        
        self.data["votes"][broadcast_id][user_id] = {
            "vote": vote,
            "timestamp": datetime.now().isoformat()
        }
        self.save_data()
        return True
    
    def get_vote_stats(self, broadcast_id: str) -> Dict:
        """Get voting statistics for a broadcast"""
        votes = self.data["votes"].get(broadcast_id, {})
        yes_count = sum(1 for v in votes.values() if v["vote"] == "Yes")
        no_count = sum(1 for v in votes.values() if v["vote"] == "No")
        return {
            "yes": yes_count,
            "no": no_count,
            "total": len(votes)
        }
    
    def update_broadcast_stats(self, broadcast_id: str, stats: Dict):
        """Update broadcast statistics"""
        if broadcast_id in self.data["broadcasts"]:
            self.data["broadcasts"][broadcast_id]["stats"] = stats
            self.save_data()
    
    def get_broadcast_history(self) -> List[Dict]:
        """Get all broadcast campaigns"""
        return [
            {
                "id": bid,
                "created_at": b["created_at"],
                "message": b["message"][:50] + "..." if len(b["message"]) > 50 else b["message"],
                "stats": b["stats"]
            }
            for bid, b in sorted(
                self.data["broadcasts"].items(),
                key=lambda x: x[1]["created_at"],
                reverse=True
            )
        ]
