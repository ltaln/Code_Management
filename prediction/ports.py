"""Integration interfaces only. No prediction algorithm or network client."""
from typing import Any, Mapping, Protocol

class DataProvider(Protocol):
    def collect(self, task: Mapping[str, Any]) -> Mapping[str, Any]: ...

class GPTExecutor(Protocol):
    def execute(self, task: Mapping[str, Any], frozen_assets: Mapping[str, bytes],
                snapshot: Mapping[str, Any]) -> Mapping[str, Any]: ...

class PredictionArchive(Protocol):
    def lookup(self, match_id: str, model_version: str) -> Mapping[str, Any]:
        """Return FOUND/NOT_FOUND/UNAVAILABLE explicitly."""
        ...

    def commit_once(self, prediction_id: str, record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Persist immutable content and return a verified commit receipt."""
        ...
