import shutil
from pathlib import Path

from steamwd.config.settings import Settings
from steamwd.core.models import WorkshopItem
from steamwd.core.naming import sanitize_filename
from steamwd.services import files


class StellarisProcessor:
    """Place a mod in Stellaris' user folder and create its ``.mod`` descriptor."""

    def process(self, source: Path, item: WorkshopItem, settings: Settings, destination: Path) -> Path:
        """Install the content and write the descriptor expected by Stellaris."""
        mod_name = sanitize_filename(item.title) or str(item.item_id)
        mod_dir = Path(settings.stellaris_mod_dir)
        destination = mod_dir / mod_name
        mod_dir.mkdir(parents=True, exist_ok=True)
        if settings.transfer_mode == "leave":
            destination = source
        else:
            files.transfer(source, destination, settings.transfer_mode)
        descriptor_path = mod_dir / f"{mod_name}.mod"
        descriptor = destination / "descriptor.mod"
        if descriptor.is_file():
            shutil.copyfile(descriptor, descriptor_path)
            lines = descriptor_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = [f'name="{item.title}"']
        lines = [line for line in lines if not line.lstrip().startswith(("path=", "remote_file_id="))]
        lines.extend((f'path="{destination.as_posix()}"', f'remote_file_id="{item.item_id}"'))
        descriptor_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return destination
