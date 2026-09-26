from typing import Any

import pytest
import requests

from steamwd.errors import SteamApiError
from steamwd.services.steam_api import SteamApi


class _Response:
    def __init__(self, body: Any, status: int = 200) -> None:
        self._body = body
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._body


class _Session:
    def __init__(self, post_body: Any = None, get_body: Any = None, status: int = 200) -> None:
        self.post_body, self.get_body, self.status = post_body, get_body, status
        self.posts: list[dict[str, Any]] = []

    def post(self, url: str, data: dict[str, Any], timeout: float) -> _Response:
        self.posts.append({"url": url, **data})
        return _Response(self.post_body, self.status)

    def get(self, url: str, params: dict[str, Any], timeout: float) -> _Response:
        return _Response(self.get_body, self.status)


def _api(session: _Session) -> SteamApi:
    return SteamApi(session=session)  # type: ignore[arg-type]


def test_item_details() -> None:
    session = _Session(
        {
            "response": {
                "publishedfiledetails": [
                    {
                        "publishedfileid": "10",
                        "result": 1,
                        "consumer_app_id": 4000,
                        "title": "Map",
                        "file_size": "2048",
                        "time_updated": 99,
                    },
                    {"publishedfileid": "11", "result": 9},
                ]
            }
        }
    )
    items, errors = _api(session).get_item_details([10, 11, 12])
    assert items[10].title == "Map"
    assert items[10].app_id == 4000
    assert items[10].file_size == 2048
    assert set(errors) == {11, 12}
    assert session.posts[0]["itemcount"] == 3
    assert session.posts[0]["publishedfileids[2]"] == 12


def test_collection_children_sorted_and_non_collections_ignored() -> None:
    session = _Session(
        {
            "response": {
                "collectiondetails": [
                    {
                        "publishedfileid": "1",
                        "result": 1,
                        "children": [
                            {"publishedfileid": "3", "sortorder": 2, "filetype": 0},
                            {"publishedfileid": "2", "sortorder": 1, "filetype": 2},
                        ],
                    },
                    {"publishedfileid": "5", "result": 1},
                ]
            }
        }
    )
    assert _api(session).get_collection_children([1, 5]) == {1: [(2, 2), (3, 0)]}


def test_http_errors_raise_api_error() -> None:
    with pytest.raises(SteamApiError):
        _api(_Session({}, status=500)).get_item_details([1])


def test_app_name_lookup_and_failure() -> None:
    api = _api(_Session(get_body={"4000": {"success": True, "data": {"name": "Garry's Mod"}}}))
    assert api.get_app_name(4000) == "Garry's Mod"
    assert _api(_Session(get_body={"1": {"success": False}})).get_app_name(1) is None
