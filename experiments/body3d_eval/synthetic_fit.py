#!/usr/bin/env python3
"""Synthetic round trip for app/ml/vision/body3d.py: does fitting recover a known body?

For random SMPL-X shapes: pose the body (arms slightly out for the front photo, down for the side
photo), render an orthographic person mask and pixel landmarks for each view, fit the model to them
with only the true height given, and compare the fitted measurements with the true ones.

This checks the fitting method, NOT real-world accuracy: real photos add perspective, clothing,
hair, imperfect MediaPipe masks and landmarks, and posture. That needs tape-measured volunteers.

Run from services/api (SMPL-X files in models/smplx, `uv sync --extra body3d`):
    uv run python ../../experiments/body3d_eval/synthetic_fit.py --bodies 8
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api"))

from app.ml.vision import body3d

KEYS = ["chest_circumference", "waist_circumference", "hip_circumference", "neck_circumference",
        "shoulder_width", "sleeve_length", "back_length"]
MP_NAMES = {v: k for k, v in body3d.MP_TO_SMPLX.items()}


def render(body, betas, kind, arm, size=(700, 1100), scale=520.0):
    torch = body.torch
    pose = torch.zeros(1, 63)
    pose[0, (body3d.L_SHOULDER - 1) * 3 + 2] = -arm
    pose[0, (body3d.R_SHOULDER - 1) * 3 + 2] = arm
    yaw = 0.0 if kind == "front" else np.pi / 2
    with torch.no_grad():
        out = body.model(betas=torch.as_tensor(betas, dtype=torch.float32)[None], body_pose=pose,
                         global_orient=torch.tensor([[0.0, yaw, 0.0]]))
    v, j = out.vertices[0].numpy(), out.joints[0].numpy()
    # place the whole figure inside the canvas: head 60 px from the top, centred horizontally
    cx = size[0] / 2 - scale * float(v[:, 0].mean())
    cy = 60 + scale * float(v[:, 1].max())
    uv = np.stack([scale * v[:, 0] + cx, -scale * v[:, 1] + cy], axis=1)
    assert uv[:, 1].max() < size[1] - 5 and uv[:, 0].min() > 5 and uv[:, 0].max() < size[0] - 5, "figure clipped"
    img = Image.new("L", size, 0)
    draw = ImageDraw.Draw(img)
    for f in body.faces:
        draw.polygon([tuple(uv[i]) for i in f], fill=255)
    mask = np.asarray(img) > 0
    juv = np.stack([scale * j[:, 0] + cx, -scale * j[:, 1] + cy], axis=1)
    landmarks = {MP_NAMES[i]: (float(juv[i, 0]), float(juv[i, 1]), 1.0) for i in MP_NAMES}
    return body3d.View(kind=kind, mask=mask, landmarks=landmarks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", type=int, default=8)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--gender", default="neutral")
    a = ap.parse_args()
    body = body3d.get_body_model(a.gender)
    rng = np.random.default_rng(7)
    errors = {k: [] for k in KEYS}
    for n in range(a.bodies):
        betas = np.zeros(body3d.NUM_BETAS)
        betas[:10] = rng.normal(0, 1.2, 10)
        truth = body3d.measure(body, betas)
        views = [render(body, betas, "front", arm=0.9), render(body, betas, "side", arm=1.35)]
        t0 = time.time()
        fitted, _diag = body3d.fit(body, views, truth["height"], steps=a.steps)
        got = body3d.measure(body, fitted)
        line = " ".join(f"{k.split('_')[0][:5]} {truth[k]:5.1f}->{got[k]:5.1f}" for k in KEYS)
        print(f"#{n} {time.time() - t0:4.1f}s h {truth['height']}->{got['height']} | {line}", flush=True)
        for k in KEYS:
            errors[k].append(got[k] - truth[k])
    print("\nselisih (cm): rata-rata mutlak | maks mutlak | bias")
    for k in KEYS:
        e = np.array(errors[k])
        print(f"  {k:22s} {np.abs(e).mean():5.1f} | {np.abs(e).max():5.1f} | {e.mean():+5.1f}")


if __name__ == "__main__":
    main()
