"""The device tracker must never hand Home Assistant a null accuracy.

Regression: `location_accuracy` returned None whenever the position came from the
cloud, because cloud fixes carry no measured accuracy. Home Assistant declares the
property `-> float` (default 0) and passes it into zone matching, where
`zone_dist - zone_radius < radius` compares a float against None. That TypeError
fires while the state is written, so Home Assistant refused to add the entity at
all and the automations that depend on it lost their tracker - while the same
machine sat parked, which is exactly when cloud accuracy is unknown.

Run: .venv\\Scripts\\python.exe -m pytest -q tests/test_tracker_accuracy.py
"""
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion"
spec = importlib.util.spec_from_file_location("accuracy_protocol", ROOT / "locator_protocol.py")
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)

accuracy_meters = protocol.accuracy_meters


def test_unknown_accuracy_becomes_zero_not_none():
    # The cloud never reports accuracy; this is the value that killed the entity.
    assert accuracy_meters(None) == 0
    assert accuracy_meters(None) is not None


def test_real_accuracy_survives():
    assert accuracy_meters(2.2) == 2.2
    assert accuracy_meters(8) == 8.0
    assert accuracy_meters(0) == 0


def test_nonsense_accuracy_collapses_to_zero():
    for value in (True, False, "8", float("nan"), float("inf"), -5, [], {}):
        assert accuracy_meters(value) == 0, value


def test_the_tracker_property_uses_it():
    """Guard the wiring, not just the helper: the entity must call the helper."""
    source = (ROOT / "device_tracker.py").read_text(encoding="utf-8")
    assert "accuracy_meters(" in source, "device_tracker no longer normalises accuracy"
    # The property is typed as float in Home Assistant; keep that visible here.
    assert "def location_accuracy(self) -> float:" in source
    assert "-> int | None" not in source
