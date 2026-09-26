"""Steam Web API client for Workshop metadata and collections (no API key needed)."""

import logging
from collections.abc import Iterator, Sequence
from typing import Any

import requests

from steamwd.core.models import WorkshopItem
from steamwd.errors import SteamApiError

__all__ = ["COLLECTION_FILE_TYPE", "SteamApi"]

logger = logging.getLogger(__name__)

_API = "https://api.steampowered.com/ISteamRemoteStorage"
_STORE_APP_DETAILS = "https://store.steampowered.com/api/appdetails"
_CHUNK = 100
COLLECTION_FILE_TYPE = 2


class SteamApi:
    """Thin client for the public Steam Web API endpoints SteamWD needs."""

    def __init__(self, timeout: float = 30, session: requests.Session | None = None) -> None:
        """Create a client.

        Args:
            timeout: Request timeout in seconds.
            session: Optional session (injected in tests).
        """
        self._timeout = timeout
        self._session = session or requests.Session()
        self._app_names: dict[int, str | None] = {}

    def get_item_details(self, item_ids: Sequence[int]) -> tuple[dict[int, WorkshopItem], dict[int, str]]:
        """Look up items.

        Returns:
            Items found, and an error message for every ID that could not be resolved.
        """
        items: dict[int, WorkshopItem] = {}
        errors: dict[int, str] = {}
        for chunk in _chunks(item_ids):
            data = self._post("GetPublishedFileDetails", "itemcount", chunk)
            for entry in data.get("publishedfiledetails", []):
                item_id = _int(entry.get("publishedfileid"))
                if item_id is None:
                    continue
                app_id = _int(entry.get("consumer_app_id"))
                if entry.get("result") != 1 or not app_id:
                    errors[item_id] = "Item not found (it may be private, removed or hidden)"
                    continue
                items[item_id] = WorkshopItem(
                    item_id=item_id,
                    title=str(entry.get("title") or item_id),
                    app_id=app_id,
                    file_size=_int(entry.get("file_size")) or 0,
                    time_updated=_int(entry.get("time_updated")) or 0,
                )
        for item_id in item_ids:
            if item_id not in items:
                errors.setdefault(item_id, "Item not found")
        return items, errors

    def get_collection_children(self, item_ids: Sequence[int]) -> dict[int, list[tuple[int, int]]]:
        """Return ``{collection_id: [(child_id, file_type), ...]}`` for IDs that are collections."""
        collections: dict[int, list[tuple[int, int]]] = {}
        for chunk in _chunks(item_ids):
            data = self._post("GetCollectionDetails", "collectioncount", chunk)
            for entry in data.get("collectiondetails", []):
                collection_id = _int(entry.get("publishedfileid"))
                children = entry.get("children") or []
                if collection_id is None or entry.get("result") != 1 or not children:
                    continue
                parsed = [
                    (child_id, _int(child.get("filetype")) or 0)
                    for child in sorted(children, key=lambda c: _int(c.get("sortorder")) or 0)
                    if (child_id := _int(child.get("publishedfileid"))) is not None
                ]
                if parsed:
                    collections[collection_id] = parsed
        return collections

    def get_app_name(self, app_id: int) -> str | None:
        """Look up a game's name from the Steam Store (cached). Returns ``None`` on failure."""
        if app_id in self._app_names:
            return self._app_names[app_id]
        name: str | None = None
        try:
            response = self._session.get(_STORE_APP_DETAILS, params={"appids": app_id}, timeout=self._timeout)
            response.raise_for_status()
            entry = response.json().get(str(app_id), {})
            if entry.get("success"):
                name = str(entry["data"]["name"])
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("Could not look up game name for app %s: %s", app_id, exc)
        self._app_names[app_id] = name
        return name

    def _post(self, method: str, count_key: str, ids: Sequence[int]) -> dict[str, Any]:
        payload: dict[str, Any] = {count_key: len(ids)}
        for index, item_id in enumerate(ids):
            payload[f"publishedfileids[{index}]"] = item_id
        url = f"{_API}/{method}/v1/"
        try:
            response = self._session.post(url, data=payload, timeout=self._timeout)
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            raise SteamApiError(f"Steam Web API request failed: {exc}") from exc
        except ValueError as exc:
            raise SteamApiError("Steam Web API returned invalid JSON") from exc
        result = body.get("response") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            raise SteamApiError("Steam Web API returned an unexpected response")
        return result


def _chunks(values: Sequence[int]) -> Iterator[list[int]]:
    for start in range(0, len(values), _CHUNK):
        yield list(values[start : start + _CHUNK])


def _int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
