from steamwd.core.parsing import parse_workshop_ids


def test_parses_ids_urls_and_steam_links() -> None:
    text = """
    123456789
    https://steamcommunity.com/sharedfiles/filedetails/?id=222&searchtext=x
    https://steamcommunity.com/workshop/filedetails/?l=english&id=333
    steam://url/CommunityFilePage/444, 555;666
    """
    result = parse_workshop_ids(text)
    assert result.ids == [123456789, 222, 333, 444, 555, 666]
    assert result.invalid == []


def test_removes_duplicates_and_reports_invalid_tokens() -> None:
    result = parse_workshop_ids("1 1 https://example.com/nope hello 0")
    assert result.ids == [1]
    assert result.invalid == ["https://example.com/nope", "hello", "0"]


def test_empty_input() -> None:
    assert parse_workshop_ids("   \n ").ids == []
