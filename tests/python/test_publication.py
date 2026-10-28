import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = "haval_h6_th_location_tracker"


def test_manifest_hacs_versions_and_translation_are_consistent():
    component = ROOT / "custom_components" / DOMAIN
    manifest = json.loads((component / "manifest.json").read_text())
    assert manifest["domain"] == DOMAIN and manifest["version"] == "1.0.0"
    assert f'VERSION = "{manifest["version"]}"' in (component / "const.py").read_text()
    assert "haval-journey-card.js?v=1.0.0" in (ROOT / "docs" / "installation.md").read_text()
    assert json.loads((component / "strings.json").read_text()) == json.loads(
        (component / "translations" / "en.json").read_text(),
    )
    assert json.loads((ROOT / "hacs.json").read_text())["country"] == "TH"
    assert len(list((ROOT / "custom_components").iterdir())) == 1


def test_manual_links_and_explicit_synthetic_images_exist():
    for path in [*ROOT.glob("*.md"), *ROOT.joinpath("docs").glob("*.md")]:
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            assert (path.parent / target.partition("#")[0]).is_file(), (path.name, target)
    for name in ("setup", "journeys", "stops", "no-gps"):
        assert (ROOT / "docs" / "images" / f"{name}.png").read_bytes().startswith(b"\x89PNG")
    assert "SYNTHETIC DEMONSTRATION" in (ROOT / "docs" / "demo" / "index.html").read_text()
    fixture = json.loads((ROOT / "docs" / "demo" / "journey-fixture.json").read_text())
    assert fixture["synthetic"] is True and fixture["sample_count"] == 26


def test_production_companion_has_no_cloud_signin_or_vehicle_command_surface():
    component = ROOT / "custom_components" / DOMAIN
    for path in component.glob("*.py"):
        text = path.read_text()
        assert not any(token in text for token in (
            "access_token", "refresh_token", "thailand_control", "call_service",
            "create_thailand", "findStatus", "authenticate(", "get_last_status(",
        )), path.name
    assert "async_request_refresh" not in (component / "source.py").read_text()


def test_allowlisted_source_tree_is_clean():
    spec = importlib.util.spec_from_file_location("public_scan", ROOT / "scripts" / "check_public_tree.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.scan(ROOT)
    assert len(files) >= 40
