"""
database.py — MongoDB connection manager.
Singleton pattern: connection is established once and reused across the app.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import config

# Global variables to hold the shared connection state
_client          = None
_db              = None
_connection_type = None   # 'local'


def _try_connect(uri: str, label: str, timeout_ms: int = 5000):
    """
    Attempts to establish a connection to a specific MongoDB instance.
    The ping command ensures we're actually connected and not just pointing
    at an unreachable socket.
    """
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command('ping')   # This will raise an exception if the DB is unreachable
    return client


def get_db():
    """
    The main entry point for database access. If a connection is already open,
    it returns it. Otherwise, it tries to connect to the local instance.
    """
    global _client, _db, _connection_type

    # Reuse existing connection if possible
    if _db is not None:
        return _db, _connection_type

    # Try connecting to the local MongoDB instance (or whatever URI is in config)
    try:
        _client          = _try_connect(config.LOCAL_URI, 'Local', timeout_ms=3000)
        _db              = _client[config.DB_NAME]
        _connection_type = 'local'
        print("[DB] Successfully connected to Local MongoDB.")
        return _db, _connection_type
    except Exception as local_err:
        # If we can't even get a local connection, we crash the app because we can't do anything
        raise RuntimeError(
            f"[DB] Could not connect to Local MongoDB instance.\n"
            f"  Error : {local_err}"
        )


def get_connection_type() -> str:
    """Helper to check if we're connected or offline."""
    if _connection_type:
        return _connection_type
    try:
        # Try to initialize the DB if it hasn't been yet
        _, ct = get_db()
        return ct
    except Exception:
        return 'disconnected'


def reset_connection():
    """
    Utility to wipe the current connection state. Useful for recovery
    scenarios or if the server goes down and we need a clean slate.
    """
    global _client, _db, _connection_type
    if _client:
        try:
            _client.close()
        except Exception:
            pass
    _client = _db = _connection_type = None
