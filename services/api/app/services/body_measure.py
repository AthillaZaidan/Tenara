"""Body-dimension estimates from pose landmarks and the user's height.

Honest scope: one front photo supports only a few linear dimensions. Circumferences and arm length are
NOT inferred; they are returned as manual_required so nothing is invented.
"""
import math

from app.services.measurements import DIMENSION_RANGES
from app.services.pose import PoseResult

# Anthropometric ratios (fraction of stature) used only for scale calibration.
NOSE_TO_ANKLE = 0.897
SHOULDER_TO_HIP = 0.288
MIN_VISIBILITY = 0.5
SUPPORTED = ("shoulder_width", "back_length")


class MeasurementFailure(Exception):
    """Input unsuitable for any estimate: ask the user to retake the photo."""


def _px(a, b, size) -> float:
    return math.hypot((a.x - b.x) * size[0], (a.y - b.y) * size[1])


def _mid(a, b):
    from app.services.pose import Landmark

    return Landmark((a.x + b.x) / 2, (a.y + b.y) / 2, min(a.visibility, b.visibility))


def estimate(pose: PoseResult, height_cm: float, image_size: tuple[int, int]) -> dict:
    if pose.pose_count == 0:
        raise MeasurementFailure("Tidak ada orang yang terdeteksi. Gunakan foto seluruh badan, "
                                 "satu orang, menghadap depan.")
    if pose.pose_count > 1:
        raise MeasurementFailure("Terdeteksi lebih dari satu orang. Gunakan foto satu orang saja.")
    m = pose.landmarks
    for name in ("l_shoulder", "r_shoulder", "l_hip", "r_hip"):
        if m[name].visibility < MIN_VISIBILITY:
            raise MeasurementFailure("Bahu dan pinggul harus terlihat jelas. Hindari penghalang "
                                     "dan pakai pakaian pas badan.")
    shoulder_mid = _mid(m["l_shoulder"], m["r_shoulder"])
    hip_mid = _mid(m["l_hip"], m["r_hip"])
    torso_px = _px(shoulder_mid, hip_mid, image_size)
    warnings = ["buyer_review_required"]
    quality = "review_required"

    ankles_visible = min(m["l_ankle"].visibility, m["r_ankle"].visibility) >= MIN_VISIBILITY
    if ankles_visible:
        ankle_mid = _mid(m["l_ankle"], m["r_ankle"])
        height_px = abs(ankle_mid.y - m["nose"].y) * image_size[1] / NOSE_TO_ANKLE
    else:
        height_px = torso_px / SHOULDER_TO_HIP
        quality = "low_confidence"
        warnings.append("scale_from_torso_proportion: kaki tidak terlihat jelas, skala kurang akurat")
    px_per_cm = height_px / height_cm

    values = {}
    raw = {"shoulder_width": _px(m["l_shoulder"], m["r_shoulder"], image_size) / px_per_cm,
           "back_length": torso_px / px_per_cm}
    for key in DIMENSION_RANGES:
        if key not in SUPPORTED:
            values[key] = {"value_cm": None, "source": "manual_required",
                           "quality_flag": "unsupported"}
            continue
        lo, hi = DIMENSION_RANGES[key]
        value = round(raw[key], 1)
        if not (lo <= value <= hi):
            values[key] = {"value_cm": None, "source": "manual_required",
                           "quality_flag": "implausible"}
            warnings.append(f"{key}_implausible: hasil di luar rentang wajar, isi manual")
        else:
            values[key] = {"value_cm": value, "source": "estimated", "quality_flag": quality}
    return {"values": values, "warnings": warnings, "model_version": pose.model_version,
            "scale_basis": "full_height" if ankles_visible else "torso_proportion"}
