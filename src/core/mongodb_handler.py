import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MongoDBHandler:
    def __init__(self):
        self._client = None
        self._db = None
        self._collection = None
        self.connected: bool = False
        self.database_name: str = ""
        self.collection_name: str = ""
        self.last_error: str = ""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, uri: str, database: str, collection: str) -> bool:
        try:
            from pymongo import MongoClient
            from pymongo.server_api import ServerApi

            self._client = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=5000)
            self._db = self._client[database]
            self._collection = self._db[collection]

            self._client.admin.command("ping")  # verify connection

            self.connected = True
            self.database_name = database
            self.collection_name = collection
            self.last_error = ""
            logger.info(f"Connected to MongoDB: {database}.{collection}")
            return True

        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            logger.error(f"MongoDB connect failed: {exc}")
            return False

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
        self.connected = False
        self._client = None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert(self, tag_path: str, tag_name: str, value: Any, unit: str = "") -> bool:
        if not self.connected:
            return False
        try:
            doc = {
                "tag_path": tag_path,
                "tag_name": tag_name,
                "value": value,
                "unit": unit,
                "timestamp": datetime.utcnow(),
            }
            self._collection.insert_one(doc)
            return True
        except Exception as exc:
            logger.error(f"Insert error: {exc}")
            return False

    def insert_many(self, documents: List[Dict[str, Any]]) -> bool:
        if not self.connected or not documents:
            return False
        try:
            self._collection.insert_many(documents)
            return True
        except Exception as exc:
            logger.error(f"Insert many error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        tag_path: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 5000,
    ) -> List[Dict]:
        if not self.connected:
            return []
        try:
            filt: Dict[str, Any] = {"tag_path": tag_path}
            if start or end:
                ts_filter: Dict[str, Any] = {}
                if start:
                    ts_filter["$gte"] = start
                if end:
                    ts_filter["$lte"] = end
                filt["timestamp"] = ts_filter

            cursor = (
                self._collection.find(filt, {"_id": 0})
                .sort("timestamp", 1)
                .limit(limit)
            )
            return list(cursor)
        except Exception as exc:
            logger.error(f"Query error: {exc}")
            return []

    def query_hours(self, tag_path: str, hours: int = 24, limit: int = 5000) -> List[Dict]:
        start = datetime.utcnow() - timedelta(hours=hours)
        return self.query(tag_path, start=start, limit=limit)

    def get_statistics(self) -> Optional[Dict]:
        if not self.connected:
            return None
        try:
            total = self._collection.count_documents({})
            tags = self._collection.distinct("tag_path")
            first = self._collection.find_one({}, {"timestamp": 1, "_id": 0}, sort=[("timestamp", 1)])
            last = self._collection.find_one({}, {"timestamp": 1, "_id": 0}, sort=[("timestamp", -1)])
            return {
                "total_records": total,
                "unique_tags": len(tags),
                "tags": tags,
                "first_record": first["timestamp"] if first else None,
                "last_record": last["timestamp"] if last else None,
            }
        except Exception as exc:
            logger.error(f"Statistics error: {exc}")
            return None

    def get_distinct_tags(self) -> List[str]:
        if not self.connected:
            return []
        try:
            return self._collection.distinct("tag_path")
        except Exception as exc:
            logger.error(f"Distinct tags error: {exc}")
            return []

    def get_latest_values(self, tag_paths: List[str]) -> Dict[str, Any]:
        """Return the most recent stored value for each tag path."""
        if not self.connected:
            return {}
        result = {}
        for path in tag_paths:
            try:
                doc = self._collection.find_one(
                    {"tag_path": path},
                    {"value": 1, "timestamp": 1, "unit": 1, "_id": 0},
                    sort=[("timestamp", -1)],
                )
                result[path] = doc
            except Exception as exc:
                logger.warning(f"Latest value error for {path}: {exc}")
                result[path] = None
        return result
