"""Tailoring measurements from a front and a side photo, by fitting the SMPL-X body model.

    1. observe  MediaPipe (pose.py): body landmarks and a person mask for each photo.
    2. fit      PyTorch: SMPL-X shape (betas) plus arm pose and a camera per photo, so that the
                model's joints and its silhouette width row by row match both photos. The model's
                standing height is held to the buyer's stated height (that fixes the scale).
    3. measure  On the fitted body in the neutral T-pose: circumferences by cutting the mesh with a
                plane at a landmark and taking the convex hull of the cut, restricted to the right
                body part (a tape measure bridges hollows, so the hull is the right shape); lengths
                between landmarks. Definitions follow SMPL-Anthropometry (D. Bojanic, MIT licence,
                github.com/DavidBoja/SMPL-Anthropometry).

SMPL-X model files are licensed by the Max Planck Institute for NON-COMMERCIAL research and
education only; they live in models/smplx (git-ignored) and must never be committed or shipped.
Cite: Pavlakos et al., "Expressive Body Capture: 3D Hands, Face, and Body from a Single Image",
CVPR 2019. Everything here is an estimate the buyer reviews; accuracy against tape measurements has
not been established yet.
"""
from __future__ import annotations

import math
import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import settings

# SMPL-X vertex indices (SMPL-Anthropometry, landmark_definitions.py)
LM = {"HEAD_TOP": 8976, "LEFT_HEEL": 8847, "RIGHT_HEEL": 8635, "NECK_ADAM_APPLE": 8940,
      "LEFT_NIPPLE": 3572, "RIGHT_NIPPLE": 8340, "SHOULDER_TOP": 5616, "BELLY_BUTTON": 5939,
      "BACK_BELLY_BUTTON": 5941, "PUBIC_BONE": 5949, "LEFT_WRIST": 4823, "RIGHT_WRIST": 7449,
      "LEFT_SHOULDER": 4442, "RIGHT_SHOULDER": 7218}
# SMPL-X joints
PELVIS, L_HIP, R_HIP, SPINE1, L_KNEE, R_KNEE, SPINE2, L_ANKLE, R_ANKLE, SPINE3, NECK = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 16, 17, 18, 19, 20, 21
ARM_PARTS = {16, 17, 18, 19, 20, 21, *range(25, 55)}  # per-face part = joint index (smplx_parts_segm.pkl)
# measurement -> (landmarks giving the plane point, joints giving the normal, body parts kept)
CIRCUMFERENCES = {
    "neck_circumference": (["NECK_ADAM_APPLE"], (SPINE1, SPINE3), {NECK}),
    "chest_circumference": (["LEFT_NIPPLE", "RIGHT_NIPPLE"], (PELVIS, SPINE3), {SPINE2, SPINE3}),
    "waist_circumference": (["BELLY_BUTTON", "BACK_BELLY_BUTTON"], (PELVIS, SPINE3), {PELVIS, SPINE1}),
    "hip_circumference": (["PUBIC_BONE"], (PELVIS, SPINE3), {PELVIS}),
}
# MediaPipe landmark name (pose.py) -> SMPL-X joint
MP_TO_SMPLX = {"l_shoulder": L_SHOULDER, "r_shoulder": R_SHOULDER, "l_elbow": L_ELBOW, "r_elbow": R_ELBOW,
               "l_wrist": L_WRIST, "r_wrist": R_WRIST, "l_hip": L_HIP, "r_hip": R_HIP,
               "l_knee": L_KNEE, "r_knee": R_KNEE, "l_ankle": L_ANKLE, "r_ankle": R_ANKLE}
NUM_BETAS = 16
BAND_PX = 2.0
RUN_MARGIN = 0.03  # of the figure height in pixels
SIL_WEIGHT = 20.0


@dataclass
class View:
    """One photo: a person mask (H x W bool) and landmarks in pixels {name: (x, y, visibility)}."""
    kind: str  # "front" or "side"
    mask: np.ndarray
    landmarks: dict[str, tuple[float, float, float]]


class BodyModel:
    """SMPL-X loaded once; T-pose meshes for a shape, plus face part labels."""

    def __init__(self, model_dir: Path, gender: str):
        import smplx
        import torch

        self.torch = torch
        self.model = smplx.create(str(model_dir), model_type="smplx", gender=gender, num_betas=NUM_BETAS,
                                  use_pca=False, ext="npz")
        self.faces = np.asarray(self.model.faces, dtype=np.int64)
        with open(model_dir / "smplx" / "smplx_parts_segm.pkl", "rb") as fh:
            segm = pickle.load(fh, encoding="latin1")
        self.face_part = np.asarray(segm["segm"], dtype=np.int64)
        vertex_part = np.full(int(self.model.get_num_verts()), -1)
        for part in range(int(self.face_part.max()) + 1):  # a vertex takes the part of any face it is on
            vertex_part[self.faces[self.face_part == part].ravel()] = part
        self.vertex_part = vertex_part
        self.dense = _densifier(self.faces, len(vertex_part), torch)
        # trunk and legs only: a front photo's rows are used only where the arms stand clear of the
        # body, so arm points there would only pull the model's arms into the torso
        self.dense_trunk = _densifier(self.faces[~np.isin(self.face_part, list(ARM_PARTS))], len(vertex_part), torch)

    def dense_points(self, verts, trunk_only: bool = False):
        """Vertices plus edge midpoints and face centres, so a thin row of pixels always meets some."""
        return self.torch.sparse.mm(self.dense_trunk if trunk_only else self.dense, verts)

    def tpose(self, betas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        torch = self.torch
        with torch.no_grad():
            out = self.model(betas=torch.as_tensor(betas, dtype=torch.float32).reshape(1, -1), return_verts=True)
        return out.vertices[0].numpy().astype(np.float64), out.joints[0].numpy().astype(np.float64)


def _densifier(faces: np.ndarray, n_verts: int, torch):
    """Sparse matrix mapping vertices to vertices + unique edge midpoints + face centroids."""
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
    used = np.unique(faces)
    rows, cols, vals = [np.arange(len(used))], [used], [np.ones(len(used))]
    base = len(used)
    rows += [base + np.repeat(np.arange(len(edges)), 2)]
    cols += [edges.ravel()]
    vals += [np.full(2 * len(edges), 0.5)]
    base += len(edges)
    rows += [base + np.repeat(np.arange(len(faces)), 3)]
    cols += [faces.ravel()]
    vals += [np.full(3 * len(faces), 1 / 3)]
    total = base + len(faces)
    idx = torch.as_tensor(np.stack([np.concatenate(rows), np.concatenate(cols)]), dtype=torch.long)
    return torch.sparse_coo_tensor(idx, torch.as_tensor(np.concatenate(vals), dtype=torch.float32),
                                   (total, n_verts)).coalesce()


@lru_cache
def get_body_model(gender: str = "neutral") -> BodyModel | None:
    """None when SMPL-X or the optional body3d dependencies are not installed (callers fall back)."""
    model_dir = Path(settings.smplx_model_dir)
    if not (model_dir / "smplx" / f"SMPLX_{gender.upper()}.npz").exists():
        return None
    try:
        return BodyModel(model_dir, gender)
    except ImportError:
        return None


# ---------- measuring a mesh ----------

def _hull_perimeter(points: np.ndarray) -> float:
    """Perimeter of the 2D convex hull (monotone chain)."""
    pts = sorted(set(map(tuple, np.round(points, 6))))
    if len(pts) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = np.array(lower[:-1] + upper[:-1])
    return float(np.linalg.norm(np.roll(hull, -1, axis=0) - hull, axis=1).sum())


def circumference(verts: np.ndarray, faces: np.ndarray, face_part: np.ndarray, point: np.ndarray,
                  normal: np.ndarray, parts: set[int]) -> float:
    """Convex-hull length (m) of the cut through `point` with `normal`, over faces of `parts` only."""
    import trimesh

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    normal = normal / np.linalg.norm(normal)
    segments, face_idx = trimesh.intersections.mesh_plane(mesh, normal, point, return_faces=True)
    keep = np.isin(face_part[face_idx], list(parts))
    pts = segments[keep].reshape(-1, 3)
    if len(pts) < 3:
        return 0.0
    u = np.cross(normal, [1.0, 0.0, 0.0] if abs(normal[0]) < 0.9 else [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    return _hull_perimeter(np.stack([(pts - point) @ u, (pts - point) @ v], axis=1))


def measure(body: BodyModel, betas: np.ndarray) -> dict[str, float]:
    """Tailoring measurements in cm on the T-pose body of `betas`."""
    verts, joints = body.tpose(betas)

    def lm(name):
        return verts[LM[name]]

    out = {}
    for key, (landmarks, (j1, j2), parts) in CIRCUMFERENCES.items():
        point = np.mean([lm(n) for n in landmarks], axis=0)
        out[key] = 100 * circumference(verts, body.faces, body.face_part, point, joints[j2] - joints[j1], parts)
    out["shoulder_width"] = 100 * float(np.linalg.norm(lm("LEFT_SHOULDER") - lm("RIGHT_SHOULDER")))
    out["sleeve_length"] = 100 * float(np.mean([np.linalg.norm(lm("LEFT_SHOULDER") - lm("LEFT_WRIST")),
                                               np.linalg.norm(lm("RIGHT_SHOULDER") - lm("RIGHT_WRIST"))]))
    # back length: base of the neck down to the waist line, measured vertically on the standing body
    out["back_length"] = 100 * float(lm("SHOULDER_TOP")[1] - lm("BACK_BELLY_BUTTON")[1])
    out["height"] = 100 * float(lm("HEAD_TOP")[1] - (lm("LEFT_HEEL")[1] + lm("RIGHT_HEEL")[1]) / 2)
    return {k: round(v, 1) for k, v in out.items()}


# ---------- fitting the model to photos ----------

def _row_extents(mask: np.ndarray, row: int, center_x: float, margin: int) -> tuple[float, float] | None:
    """Left and right edge of the silhouette run containing center_x; None when another part of the
    figure (an arm close to the body) lies within `margin` of either edge, as the row is ambiguous."""
    line = mask[row]
    cx = round(center_x)
    if not (0 <= cx < line.size) or not line[cx]:
        return None
    left = cx
    while left > 0 and line[left - 1]:
        left -= 1
    right = cx
    while right < line.size - 1 and line[right + 1]:
        right += 1
    if line[max(0, left - margin):left].any() or line[right + 1:right + 1 + margin].any():
        return None
    return float(left), float(right)


def _arms_free_row(mask: np.ndarray, top: int, bottom: int, cx: float) -> int | None:
    """First row below `top` with figure pixels on both sides of the run around cx (arms apart)."""
    c = round(cx)
    for y in range(max(0, top), min(bottom, mask.shape[0])):
        line = mask[y]
        if not (0 <= c < line.size) or not line[c]:
            continue
        left = c
        while left > 0 and line[left - 1]:
            left -= 1
        right = c
        while right < line.size - 1 and line[right + 1]:
            right += 1
        if line[:left].any() and line[right + 1:].any():
            return y
    return None


def _profile(view: View, rows: int = 32) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Silhouette edges on rows from the shoulders to the knees, around the body's centre line."""
    lmk = view.landmarks
    ys = [lmk[n][1] for n in ("l_shoulder", "r_shoulder") if n in lmk]
    yk = [lmk[n][1] for n in ("l_knee", "r_knee") if n in lmk]
    xs = [lmk[n][0] for n in ("l_hip", "r_hip", "l_shoulder", "r_shoulder") if n in lmk]
    if not ys or not yk or not xs:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    top, bottom, cx = float(np.mean(ys)) + 4, float(np.mean(yk)), float(np.mean(xs))
    rows_with_figure = np.nonzero(view.mask.any(axis=1))[0]
    margin = math.ceil(RUN_MARGIN * float(np.ptp(rows_with_figure))) + 1 if rows_with_figure.size else 1
    if view.kind == "front":  # start where both arms have come free of the body (below the armpits)
        top = _arms_free_row(view.mask, int(top), int(bottom), cx) or top
    out_y, out_l, out_r = [], [], []
    for y in np.linspace(top, bottom, rows):
        ext = _row_extents(view.mask, round(y), cx, margin)
        if ext:
            out_y.append(y)
            out_l.append(ext[0])
            out_r.append(ext[1])
    return np.array(out_y), np.array(out_l), np.array(out_r)


TRUNK_JOINTS = (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE)


def _init_camera(model, betas, cam, view: View, s_guess: float, c_guess: tuple[float, float]):
    """Scale and centre from a least-squares fit of the trunk and leg joints to the landmarks."""
    torch = __import__("torch")
    pairs = [(MP_TO_SMPLX[n], view.landmarks[n]) for n in MP_TO_SMPLX
             if MP_TO_SMPLX[n] in TRUNK_JOINTS and n in view.landmarks and view.landmarks[n][2] >= 0.5]
    if len(pairs) < 3:
        return s_guess, torch.tensor(c_guess)
    pose = torch.zeros(1, 63)
    with torch.no_grad():
        out = model(betas=betas, body_pose=pose,
                    global_orient=torch.stack([torch.zeros(1), cam["yaw"], torch.zeros(1)], dim=1))
    j = out.joints[0].numpy()
    model_xy = np.array([[j[i, 0], -j[i, 1]] for i, _ in pairs])
    image_xy = np.array([[lm[0], lm[1]] for _, lm in pairs])
    mc, ic = model_xy.mean(0), image_xy.mean(0)
    # vertical extent is reliable in both views; horizontal collapses in the side view
    denom = float(((model_xy[:, 1] - mc[1]) ** 2).sum())
    scale = float(((model_xy[:, 1] - mc[1]) * (image_xy[:, 1] - ic[1])).sum() / denom) if denom > 1e-9 else s_guess
    if not np.isfinite(scale) or scale <= 0:
        scale = s_guess
    return scale, torch.tensor(ic - scale * mc, dtype=torch.float32)


def fit(body: BodyModel, views: list[View], height_cm: float, steps: int = 300,
        init_betas: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """Shape (betas) that explains the photos at the stated height; also returns fit diagnostics."""
    torch = body.torch
    model = body.model
    target_h = height_cm / 100.0
    start = np.zeros(NUM_BETAS) if init_betas is None else init_betas
    betas = torch.tensor(start, dtype=torch.float32).reshape(1, -1).requires_grad_(True)
    cam_params, cams = [], []
    for v in views:
        h_px = float(np.ptp(np.nonzero(v.mask.any(axis=1))[0])) or float(v.mask.shape[0])
        cx = float(np.nonzero(v.mask.any(axis=0))[0].mean())
        cy = float(np.nonzero(v.mask.any(axis=1))[0].mean())
        cam = {"yaw": torch.tensor([0.0 if v.kind == "front" else math.pi / 2], requires_grad=True),
               # relative units so one learning rate suits every parameter: log-scale and an offset in
               # figure heights (pixel units barely moved at lr 0.03 and the shape bent to compensate)
               "log_scale": torch.zeros(1, requires_grad=True),
               "offset": torch.zeros(2, requires_grad=True),
               "arms": torch.tensor([-1.2, 1.2], requires_grad=True)}  # shoulder abduction, rad
        cam_params += list(cam.values())  # only the four learnable tensors above
        cam["s0"], cam["c0"] = _init_camera(model, betas, cam, v, h_px / target_h, (cx, cy))
        cams.append(cam)
        rows, left, right = _profile(v)
        cam["rows"], cam["left"], cam["right"] = (torch.as_tensor(a, dtype=torch.float32) for a in (rows, left, right))
        names = [n for n in MP_TO_SMPLX if n in v.landmarks and v.landmarks[n][2] >= 0.5]
        cam["kp_j"] = [MP_TO_SMPLX[n] for n in names]
        cam["kp"] = torch.as_tensor([v.landmarks[n][:2] for n in names], dtype=torch.float32).reshape(-1, 2)
        cam["h_px"] = h_px
    # stage 1: cameras and arms only, shape held (as in SMPLify); stage 2: everything together
    opt_cam = torch.optim.Adam(cam_params, lr=0.03)
    opt_all = torch.optim.Adam([betas, *cam_params], lr=0.03)
    cam_steps = steps // 3
    head, heels = LM["HEAD_TOP"], [LM["LEFT_HEEL"], LM["RIGHT_HEEL"]]
    last = {}
    for step in range(steps + cam_steps):
        opt = opt_cam if step < cam_steps else opt_all
        opt.zero_grad()
        tpose = model(betas=betas)
        height = tpose.vertices[0, head, 1] - tpose.vertices[0, heels, 1].mean()
        terms = {"height": 50.0 * (height - target_h) ** 2, "prior": 0.002 * (betas ** 2).sum()}
        loss = terms["height"] + terms["prior"]
        for v, cam in zip(views, cams, strict=True):
            pose = torch.zeros(1, 63)
            pose[0, (L_SHOULDER - 1) * 3 + 2] = cam["arms"][0]
            pose[0, (R_SHOULDER - 1) * 3 + 2] = cam["arms"][1]
            out = model(betas=betas, body_pose=pose,
                        global_orient=torch.stack([torch.zeros(1), cam["yaw"], torch.zeros(1)], dim=1))
            verts, joints = out.vertices[0], out.joints[0]

            def project(p, cam=cam):
                scale = cam["s0"] * torch.exp(cam["log_scale"])
                t = cam["c0"] + cam["offset"] * cam["h_px"]
                return torch.stack([scale * p[:, 0] + t[0], -scale * p[:, 1] + t[1]], dim=1)

            norm = cam["h_px"] ** 2
            if len(cam["kp_j"]):
                kp_w = 0.0 if v.kind == "side" else 1.0  # side view: arms hide in profile
                terms[f"kp_{v.kind}"] = kp_w * ((project(joints[cam["kp_j"]]) - cam["kp"]) ** 2).sum() / norm
                loss = loss + terms[f"kp_{v.kind}"]
            if len(cam["rows"]):
                pv = project(body.dense_points(verts, trunk_only=v.kind == "front"))
                x = pv[:, 0][None, :].expand(len(cam["rows"]), -1)
                margin = RUN_MARGIN * cam["h_px"]
                # vertices on this row that fall in the photo's silhouette run (with a margin): an arm
                # separated from the body is left out on both sides, an arm touching it is kept on both
                band = ((pv[:, 1][None, :] - cam["rows"][:, None]).abs() < BAND_PX) \
                    & (x > cam["left"][:, None] - margin) & (x < cam["right"][:, None] + margin)
                right_edge = torch.where(band, x, torch.full_like(x, -1e9)).max(dim=1).values
                left_edge = torch.where(band, x, torch.full_like(x, 1e9)).min(dim=1).values
                ok = band.any(dim=1)  # the outermost vertex near each row: an unbiased edge
                if ok.any():
                    sil = ((right_edge - cam["right"])[ok] ** 2 + (left_edge - cam["left"])[ok] ** 2).mean()
                    terms[f"sil_{v.kind}"] = SIL_WEIGHT * sil / norm * int(ok.sum())
                    loss = loss + terms[f"sil_{v.kind}"]
            # the whole figure spans the mask: top of the head to the heels
            ys = project(verts)[:, 1]
            terms[f"span_{v.kind}"] = ((ys.max() - ys.min()) - cam["h_px"]) ** 2 / norm
            loss = loss + terms[f"span_{v.kind}"]
        loss.backward()
        opt.step()
        last = {"loss": float(loss.detach()), "height_cm": round(float(height.detach()) * 100, 1),
                "terms": {k: round(float(t.detach()), 5) for k, t in terms.items()},
                "cams": [{"yaw": round(float(c["yaw"]), 3), "arms": [round(float(x), 3) for x in c["arms"]]}
                         for c in cams]}
    return betas.detach().numpy()[0], last
