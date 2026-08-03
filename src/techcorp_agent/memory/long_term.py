"""A durable, long-term memory store for user facts (Module 15, Lab C).

Short-term memory (the checkpointer in ``checkpointing.py``) remembers *this
conversation*: its scope is one ``thread_id`` and it holds the message history.
Long-term memory is different in both scope and lifetime — it holds durable
facts about a *user* ("Priya is in Engineering and prefers short answers") that
should apply across *every* future conversation, even brand-new threads.

LangGraph 1.2 does ship a ``langgraph.store`` API (``BaseStore`` /
``SqliteStore``) built around namespaced, embedding-indexed items. That machinery
is powerful but heavier than this lesson needs, and its search-oriented shape
would distract from the one idea we want to teach: *a keyed bag of user facts
that survives a restart*. So this module deliberately implements a tiny,
transparent SQLite key/value store of its own — one table, three methods — which
a learner can read end to end and inspect with the ``sqlite3`` CLI.

Design:

- one row per ``(user_id, key)``, value stored as text;
- :meth:`remember` upserts a fact; :meth:`recall` returns all of a user's facts
  as a plain ``dict``;
- :func:`inject_preferences` turns a recalled dict into a single ``system`` note
  prepended to a prompt, so the agent's answers reflect what it knows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from techcorp_agent.schemas import ChatMessage

_PREFERENCES_PREFIX = "Known facts about the current user"


class UserMemoryStore:
    """A minimal SQLite-backed key/value store of durable per-user facts.

    Persistence is the whole point: a store opened on the same ``db_path`` in a
    later process (a new "session") recalls everything a previous session
    remembered. Kept intentionally tiny so it can be taught and audited directly.
    """

    def __init__(self, db_path: str | Path):
        # ``check_same_thread=False`` mirrors the checkpointer setup and keeps the
        # store usable from the graph's worker thread; access here is serialized.
        self._path = str(db_path)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id TEXT NOT NULL,
                key     TEXT NOT NULL,
                value   TEXT NOT NULL,
                PRIMARY KEY (user_id, key)
            )
            """
        )
        self._conn.commit()

    def remember(self, user_id: str, key: str, value: str) -> None:
        """Store (or overwrite) one durable fact for ``user_id``.

        Upsert semantics: remembering the same key again updates the value, so a
        user's preferences can evolve without piling up duplicate rows.
        """
        self._conn.execute(
            """
            INSERT INTO user_memory (user_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
            """,
            (user_id, key, str(value)),
        )
        self._conn.commit()

    def recall(self, user_id: str) -> dict[str, str]:
        """Return every remembered fact for ``user_id`` as a ``{key: value}`` dict.

        An unknown user yields an empty dict — a new employee simply has no facts
        yet, which the agent treats as "no preferences to apply".
        """
        rows = self._conn.execute(
            "SELECT key, value FROM user_memory WHERE user_id = ? ORDER BY key",
            (user_id,),
        ).fetchall()
        return {key: value for key, value in rows}

    def forget(self, user_id: str, key: str | None = None) -> None:
        """Delete one fact (``key`` given) or all facts for a user (``key=None``).

        Included for the privacy discussion in ``concepts.md``: a durable store of
        user data needs a deletion path (the GDPR "right to erasure").
        """
        if key is None:
            self._conn.execute("DELETE FROM user_memory WHERE user_id = ?", (user_id,))
        else:
            self._conn.execute(
                "DELETE FROM user_memory WHERE user_id = ? AND key = ?", (user_id, key)
            )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying connection (data is already durable on disk)."""
        self._conn.close()


def _is_preferences_note(message: ChatMessage) -> bool:
    """True when a message is a preferences note we previously injected."""
    return message.role == "system" and message.content.startswith(_PREFERENCES_PREFIX)


def inject_preferences(
    messages: list[ChatMessage],
    prefs: dict[str, str],
) -> list[ChatMessage]:
    """Prepend a ``system`` note describing known user facts to ``messages``.

    Turns a recalled preferences dict into one compact instruction the model can
    act on — e.g. "department: Engineering; preferred_answer_length: short" —
    placed at the very front so it frames the whole reply. With no preferences
    (empty dict) the messages are returned unchanged, so a first-time user pays
    no prompt overhead.

    Any previously injected preferences note is replaced rather than duplicated,
    so re-applying preferences across turns never stacks up.
    """
    if not prefs:
        return list(messages)

    rendered = "; ".join(f"{key}: {value}" for key, value in prefs.items())
    note = ChatMessage(
        role="system",
        content=(f"{_PREFERENCES_PREFIX} (apply them when answering): {rendered}."),
    )
    remaining = [m for m in messages if not _is_preferences_note(m)]
    return [note, *remaining]
