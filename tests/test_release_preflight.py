import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("release_preflight", Path(__file__).resolve().parents[1] / "scripts/check_release.py")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def test_rejects_same_code_and_mismatched_tag():
    with pytest.raises(ValueError, match="versionCode"):
        preflight.validate_metadata("0.2.0-beta.2", "v0.2.0-beta.2", 13, 13)
    with pytest.raises(ValueError, match="tag"):
        preflight.validate_metadata("0.2.0-beta.2", "0.2.0", 14, 13)
    preflight.validate_metadata("0.2.0-beta.3", "v0.2.0-beta.3", 14, 13)
