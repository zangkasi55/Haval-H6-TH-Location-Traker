"""Build a source-only install archive after publication checks."""

import hashlib
import json
import zipfile
from pathlib import Path

from check_public_tree import DOMAIN, scan


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = scan(root)
    version = json.loads((root / "custom_components" / DOMAIN / "manifest.json").read_text())["version"]
    output = root / "dist" / version
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"haval-h6-th-location-tracker-{version}.zip"
    selected = [
        path for path in files if path.relative_to(root).parts[:2] == ("custom_components", DOMAIN)
        or path.relative_to(root).as_posix() in {"LICENSE", "NOTICE.md", "hacs.json", "dashboards/haval-journeys.yaml"}
    ]
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(selected):
            raise ValueError("Install archive verification failed")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    print(f"Built {destination.name}: {len(selected)} members, SHA256 {digest}")


if __name__ == "__main__":
    main()
