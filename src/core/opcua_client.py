"""
OPC UA client wrapper using asyncua.sync.Client.

asyncua.sync.Client runs a persistent background event loop in a daemon thread,
so all operations (connect, read, browse) share the same loop and transport.
This avoids the 'NoneType proactor' failure that occurs when asyncio.run() is
called multiple times — each call would destroy and recreate the event loop,
invalidating the asyncua transport that was bound to the previous one.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OPCUAClient:
    def __init__(self):
        self._client = None   # asyncua.sync.Client
        self.connected: bool = False
        self.server_url: str = ""
        self.last_error: str = ""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(
        self,
        server_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        try:
            from asyncua.sync import Client as SyncClient

            self._client = SyncClient(server_url)

            if username and password:
                self._client.set_user(username)
                self._client.set_password(password)

            self._client.connect()
            # smoke test
            self._client.get_namespace_array()

            self.connected = True
            self.server_url = server_url
            self.last_error = ""
            logger.info(f"Connected to OPC UA: {server_url}")
            return True

        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            self._client = None
            logger.error(f"OPC UA connect failed: {exc}")
            return False

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self.connected = False
        self._client = None

    def verify(self) -> bool:
        if not self._client or not self.connected:
            return False
        try:
            self._client.get_namespace_array()
            return True
        except Exception:
            self.connected = False
            return False

    # ------------------------------------------------------------------
    # Node browsing
    # ------------------------------------------------------------------

    def browse_node(self, node_id: Optional[str] = None) -> list:
        """Return immediate children of node_id (None = Objects folder root)."""
        if not self.connected or not self._client:
            return []
        try:
            from asyncua import ua

            if node_id is None:
                node = self._client.get_node(ua.ObjectIds.ObjectsFolder)
            else:
                node = self._client.get_node(node_id)

            children = node.get_children()
            result = []
            for child in children:
                try:
                    node_class = child.read_node_class()
                    browse_name = child.read_browse_name()
                    display_name = child.read_display_name()
                    child_id = child.nodeid.to_string()

                    name = (display_name.Text if display_name and display_name.Text
                            else str(browse_name.Name) if browse_name else child_id)

                    is_var = (node_class == ua.NodeClass.Variable)

                    value = None
                    if is_var:
                        try:
                            raw = child.read_value()
                            value = round(float(raw), 6) if isinstance(raw, (int, float)) else raw
                        except Exception:
                            pass

                    result.append({
                        "node_id": child_id,
                        "name": name,
                        "node_class": "Variable" if is_var else "Object",
                        "value": value,
                    })
                except Exception:
                    continue

            return result

        except Exception as exc:
            self.last_error = str(exc)
            logger.error(f"browse_node failed: {exc}")
            return []

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read_tag(self, tag_path: str) -> Optional[Any]:
        if not self._client:
            return None
        try:
            node = self._client.get_node(tag_path)
            return node.read_value()
        except Exception as exc:
            logger.error(f"read_tag error ({tag_path}): {exc}")
            return None

    def read_tags(self, tag_paths: List[str]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for path in tag_paths:
            results[path] = self.read_tag(path)
        return results

    def read_tags_with_timestamp(self, tag_paths: List[str]) -> List[Dict[str, Any]]:
        raw = self.read_tags(tag_paths)
        ts = datetime.now()
        return [{"path": p, "value": v, "timestamp": ts} for p, v in raw.items()]
