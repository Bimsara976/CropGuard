"""
database.py — MongoDB connection manager.
Singleton pattern: connection is established once and reused.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import config

_client          = None
_db              = None
_connection_type = None   # 'local'


def _try_connect(uri: str, label: str, timeout_ms: int = 5000):
    """Attempt a connection and return client or raise on failure."""
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command('ping')   # Raises if unreachable
    return client


def get_db():
    """Return (db, connection_type). Tries to connect to Local MongoDB."""
    global _client, _db, _connection_type

    if _db is not None:
        return _db, _connection_type

    # Try Local
    try:
        _client          = _try_connect(config.LOCAL_URI, 'Local', timeout_ms=3000)
        _db              = _client[config.DB_NAME]
        _connection_type = 'local'
        print("[DB] Connected to Local MongoDB.")
        return _db, _connection_type
    except Exception as local_err:
        raise RuntimeError(
            f"[DB] Could not connect to Local MongoDB instance.\n"
            f"  Error : {local_err}"
        )


def get_connection_type() -> str:
    """Return 'local' or 'disconnected'."""
    if _connection_type:
        return _connection_type
    try:
        _, ct = get_db()
        return ct
    except Exception:
        return 'disconnected'


def reset_connection():
    """Force a fresh reconnection on next call to get_db()."""
    global _client, _db, _connection_type
    if _client:
        try:
            _client.close()
        except Exception:
            pass
    _client = _db = _connection_type = None
