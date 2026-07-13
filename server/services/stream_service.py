# services/stream_service.py
from typing import Dict, Optional, Any
import asyncio

# Dictionary to store active stream tasks, keyed by session_id
stream_tasks: Dict[str, asyncio.Task[Any]] = {}

# Last-known progress per session (for page refresh recovery)
session_progress: Dict[str, Dict[str, Any]] = {}

def add_stream_task(session_id: str, task: asyncio.Task[Any]) -> None:
    """
    Add a stream task for the given session_id.

    Args:
        session_id (str): Unique identifier for the session.
        task: The task object to associate with the session.
    """
    stream_tasks[session_id] = task

def remove_stream_task(session_id: str) -> None:
    """
    Remove the stream task associated with the given session_id.

    Args:
        session_id (str): Unique identifier for the session.
    """
    stream_tasks.pop(session_id, None)

def get_stream_task(session_id: str) -> Optional[asyncio.Task[Any]]:
    """
    Retrieve the stream task associated with the given session_id.

    Args:
        session_id (str): Unique identifier for the session.

    Returns:
        The task object if found, otherwise None.
    """
    return stream_tasks.get(session_id)


def update_session_progress(
    session_id: str,
    *,
    last_progress: Optional[str] = None,
    pending_type: Optional[str] = None,
) -> None:
    if not session_id:
        return
    if session_id not in session_progress:
        session_progress[session_id] = {}
    if last_progress is not None:
        session_progress[session_id]["last_progress"] = last_progress
    if pending_type is not None:
        session_progress[session_id]["pending_type"] = pending_type


def clear_session_progress(session_id: str) -> None:
    session_progress.pop(session_id, None)


def get_chat_status(session_id: str) -> Dict[str, Any]:
    task = stream_tasks.get(session_id)
    running = task is not None and not task.done()
    progress = session_progress.get(session_id, {})
    pending_type = progress.get("pending_type")
    if running and not pending_type:
        pending_type = "text"
    return {
        "running": running,
        "last_progress": progress.get("last_progress"),
        "pending_type": pending_type if running else None,
    }
