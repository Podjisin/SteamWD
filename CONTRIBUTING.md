# Contributing to SteamWD

Thanks for helping improve SteamWD. Contributions are welcome, especially
game-specific mod processors and fixes that make downloads safer and easier to
understand.

## Development setup

SteamWD requires Python 3.12 or newer on Windows.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the application with:

```powershell
python -m steamwd
```

## Checks before submitting

Run the full test and quality checks:

```powershell
pytest
ruff check src tests
ruff format --check src tests
mypy src tests
```

Keep tests deterministic and avoid making live Steam requests in tests. Use
the existing fakes and injected interfaces as examples.

## Adding a game processor module

Game processors live in `src/steamwd/processors/`. The generic processor is
used automatically for games without specialized support.

### Module structure

For example, a processor for a game with Steam app ID `123456` would start
with this module:

```python
# src/steamwd/processors/example_game.py
from pathlib import Path

from steamwd.config.settings import Settings
from steamwd.core.models import WorkshopItem
from steamwd.services import files


class ExampleGameProcessor:
    """Install Example Game Workshop mods into its user mod folder."""

    def process(self, source: Path, item: WorkshopItem, settings: Settings, destination: Path) -> Path:
        mod_name = item.title or str(item.item_id)
        destination = Path(settings.example_game_mod_dir) / mod_name
        if settings.transfer_mode == "leave":
            return source
        return files.transfer(source, destination, settings.transfer_mode)
```

Register the module and its display name in
`src/steamwd/processors/__init__.py`:

```python
from steamwd.processors.example_game import ExampleGameProcessor

_PROCESSORS: dict[int, tuple[str, ModProcessor]] = {
    # Existing processors...
    123456: ("Example Game", ExampleGameProcessor()),
}
```

If the game requires special metadata, generate or update it in the processor.
Do not put game-specific behavior in `DownloadManager`.

### Required integration steps

To add support for a game:

1. Create a processor module implementing `ModProcessor`.
2. Use the Workshop item app ID to determine the game-specific destination.
3. Preserve the game's expected metadata and folder structure.
4. Add the processor to the registry in `src/steamwd/processors/__init__.py`.
5. Add a destination field to `Settings` if the path should be editable:
   
   ```python
   example_game_mod_dir: str = field(default_factory=lambda: str(paths.default_example_game_mod_dir()))
   ```

   Also add the field to `PATH_FIELDS`, the Settings view, and
   `src/steamwd/config/paths.py` as appropriate.
6. Add tests under `tests/processors/` covering normal processing and important
   edge cases.
7. Update `README.md` and `CHANGELOG.md` when the processor is user-visible.

At minimum, test that the processor places the content in the expected folder,
preserves required metadata, and handles `copy`, `move`, and `leave` modes as
appropriate.

Processors should be small and focused. Keep download orchestration in
`DownloadManager`; game-specific file handling belongs in the processor.

## Pull requests

- Explain what changed and why.
- Include tests for new behavior or bug fixes.
- Mention any game-specific assumptions or required paths.
- Do not include credentials, personal paths, downloaded Workshop content, or
  generated build artifacts.
- Keep unrelated formatting and refactoring out of the change.

## Building the executable

The standalone executable can be built locally with:

```powershell
scripts\build.ps1
```

The output is written to `dist\SteamWD.exe`.
