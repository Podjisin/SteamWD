import pytest

from steamwd.core.naming import render_folder_name, sanitize_filename, validate_template


@pytest.mark.parametrize("template", ["{title}", "{id} - {title}", "{game}/{id}", "{appid}_{id}"])
def test_valid_templates(template: str) -> None:
    assert validate_template(template) is None


@pytest.mark.parametrize(
    ("template", "fragment"),
    [
        ("", "empty"),
        ("{name}", "unknown field"),
        ("{id:>10}", "format specifiers"),
        ("{game}", "must contain"),
        ("{title", "invalid template"),
    ],
)
def test_invalid_templates(template: str, fragment: str) -> None:
    error = validate_template(template)
    assert error is not None
    assert fragment in error


def test_render_sanitizes_and_falls_back() -> None:
    name = render_folder_name("{id} - {title}", item_id=5, title='A/B: "C"?', app_id=1, game="G")
    assert name == "5 - A_B_ _C__"
    assert render_folder_name("{title}", item_id=7, title="", app_id=1, game="") == "7"


def test_sanitize_reserved_and_trailing() -> None:
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("  name.  ") == "name"
    assert len(sanitize_filename("x" * 500)) == 120
