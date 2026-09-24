from __future__ import annotations
import abc


class ChatAdapter(abc.ABC):
    """A channel between the human and neo. read() returns the next human
    message or None to end the session; write() delivers neo's reply."""

    @abc.abstractmethod
    def read(self) -> str | None: ...

    @abc.abstractmethod
    def write(self, text: str) -> None: ...
