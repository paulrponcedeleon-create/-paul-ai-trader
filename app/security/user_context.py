from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_current_user_id: ContextVar[str] = ContextVar("current_user_id", default="owner")


def get_current_user_id() -> str:
    return _current_user_id.get()


def set_current_user_id(user_id: str) -> None:
    _current_user_id.set(str(user_id or "owner"))


@contextmanager
def user_scope(user_id: str) -> Iterator[None]:
    token = _current_user_id.set(str(user_id or "owner"))
    try:
        yield
    finally:
        _current_user_id.reset(token)
