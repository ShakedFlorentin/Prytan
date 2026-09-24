from __future__ import annotations
from core.runtime.adapters.base import ChatAdapter


class CliAdapter(ChatAdapter):
    def __init__(self, input_fn=input, output_fn=print, speaker="atlas"):
        self._input = input_fn
        self._output = output_fn
        self._speaker = speaker

    def read(self) -> str | None:
        try:
            line = self._input("you > ")
        except EOFError:
            return None
        line = line.strip()
        return line or None   # blank line ends the session

    def write(self, text: str) -> None:
        self._output(f"{self._speaker} > {text}")
