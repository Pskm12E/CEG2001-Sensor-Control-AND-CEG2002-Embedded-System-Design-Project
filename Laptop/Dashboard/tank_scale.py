"""The car tank calibration shared by the local dashboard and docking relay."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def validate(points):
    """Check partial or complete raw ADC calibration and return the supplied mapping."""
    if (not isinstance(points, dict) or points.keys() - {"empty", "full"}
            or any(type(v) is not int or not 0 <= v <= 4095 for v in points.values())):
        raise ValueError("Tank calibration requires raw readings from 0 to 4095.")
    if "empty" in points and "full" in points and points["full"] <= points["empty"]:
        raise ValueError("Full must read higher than empty.")
    return points


def path():
    """Return the per-user location shared by the dashboard and car build helper."""
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "PlantRobotShare" / "tank.json"


def load():
    """Read valid local calibration, returning None if it is missing or malformed."""
    try:
        return validate(json.loads(path().read_text(encoding="utf-8-sig")))
    except (OSError, ValueError):
        return None


def save(points):
    """Validate the endpoints and atomically replace the on-disk calibration."""
    validate(points)
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = NamedTemporaryFile(mode="w", dir=target.parent, delete=False, encoding="utf-8")
    name = Path(temp.name)
    try:
        with temp:
            json.dump(points, temp)
        os.replace(name, target)
    finally:
        name.unlink(missing_ok=True)


def departure_raw(points):
    """Return the first raw count strictly above 60%, or None until both endpoints exist."""
    if not points or "empty" not in points or "full" not in points:
        return None
    # First ADC count strictly above 60%, without display rounding.
    return points["empty"] + 3 * (points["full"] - points["empty"]) // 5 + 1
