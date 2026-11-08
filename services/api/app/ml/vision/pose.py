"""Pose landmarks from a still photo (MediaPipe Pose Landmarker, runs locally)."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from PIL import Image

from app.core.config import settings

LANDMARK_INDEX = {"nose": 0, "l_shoulder": 11, "r_shoulder": 12, "l_elbow": 13, "r_elbow": 14,
                  "l_wrist": 15, "r_wrist": 16, "l_hip": 23, "r_hip": 24, "l_knee": 25, "r_knee": 26,
                  "l_ankle": 27, "r_ankle": 28, "l_heel": 29, "r_heel": 30, "l_foot_index": 31,
                  "r_foot_index": 32}


@dataclass
class Landmark:
    x: float  # normalised 0..1 over image width
    y: float  # normalised 0..1 over image height
    visibility: float


@dataclass
class PoseResult:
    pose_count: int
    landmarks: dict[str, Landmark]
    model_version: str
    mask: object | None = None  # person mask (H x W bool numpy array) of the first person, when available


class PoseDetector(Protocol):
    model_version: str

    def detect(self, image: Image.Image) -> PoseResult: ...


class MediaPipePoseDetector:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._landmarker = None
        import mediapipe

        self.model_version = f"mediapipe-pose-landmarker-full/{mediapipe.__version__}"

    def _load(self):
        if self._landmarker is None:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            options = vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=self.model_path), num_poses=2,
                output_segmentation_masks=True)
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def detect(self, image: Image.Image) -> PoseResult:
        import mediapipe as mp
        import numpy as np

        frame = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=np.ascontiguousarray(np.asarray(image.convert("RGB"))))
        result = self._load().detect(frame)
        if not result.pose_landmarks:
            return PoseResult(0, {}, self.model_version)
        first = result.pose_landmarks[0]
        marks = {name: Landmark(first[i].x, first[i].y, float(first[i].visibility or 0.0))
                 for name, i in LANDMARK_INDEX.items()}
        mask = None
        if result.segmentation_masks:
            mask = np.asarray(result.segmentation_masks[0].numpy_view()).squeeze() > 0.5
        return PoseResult(len(result.pose_landmarks), marks, self.model_version, mask)


@lru_cache
def get_pose_detector() -> PoseDetector | None:
    """None when the model file is not installed; callers then fail honestly (no fake output)."""
    if not Path(settings.pose_model_path).exists():
        return None
    try:
        return MediaPipePoseDetector(settings.pose_model_path)
    except ImportError:
        return None
