"""Conceptual garment illustrations built from the listing's own fabric photo.

Not a pattern, not a fit simulation: a flat garment shape per template filled with the actual fabric
texture, with the accepted options drawn on it. Anything we cannot draw is reported in `warnings`.
"""
import io
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageOps, ImageStat

from app.services.pose import PoseResult

W, H = 600, 800
CX = 300
SHOULDER_Y = 140
SHOULDER_L, SHOULDER_R = 190, 410  # canonical shoulder span used to scale onto a photo
OUTLINE = (58, 47, 42, 255)
PX_PER_CM = 6
GEOM = {  # template -> (body length px, sleeve kind, sleeve length px)
    "T01": (330, "short", 95), "T02": (320, "mid", 190), "T03": (300, None, 0),
    "T04": (420, "long", 290), "T05": (450, "long", 250),
}
BUTTON_COLORS = {"plain_01": (244, 240, 230), "wood_option_01": (139, 90, 43),
                 "shell_option_01": (232, 228, 220)}
HANDLED = {"collar", "pockets", "closure", "buttons", "hem_length_delta_cm", "sleeve_length_delta_cm",
           "trim", "motif_placement"}


@dataclass
class Rendered:
    image: Image.Image
    drawn: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_texture(data: bytes, size: int = 180) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    return img.crop((left, top, left + side, top + side)).resize((size, size))


def _tiled(texture: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (W, H))
    for x in range(0, W, texture.width):
        for y in range(0, H, texture.height):
            canvas.paste(texture, (x, y))
    return canvas


def _mean(texture: Image.Image) -> tuple[int, int, int]:
    r, g, b = ImageStat.Stat(texture).mean[:3]
    return int(r), int(g), int(b)


def render_garment(code: str, state: dict, texture: Image.Image) -> Rendered:
    body_len, sleeve_kind, sleeve_len = GEOM[code]
    body_len = int(body_len + (state.get("hem_length_delta_cm") or 0) * PX_PER_CM)
    sleeve_len = int(max(30, sleeve_len + (state.get("sleeve_length_delta_cm") or 0) * PX_PER_CM)) \
        if sleeve_kind else 0
    hem_y = SHOULDER_Y + body_len
    out = Rendered(Image.new("RGBA", (W, H), (0, 0, 0, 0)))

    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    torso = [(SHOULDER_L, SHOULDER_Y), (SHOULDER_R, SHOULDER_Y), (SHOULDER_R - 8, hem_y),
             (SHOULDER_L + 8, hem_y)]
    md.polygon(torso, fill=255)
    sleeves = []
    if sleeve_kind:
        dx, dy = int(-0.55 * sleeve_len), int(0.84 * sleeve_len)
        for sign in (-1, 1):
            edge = SHOULDER_L if sign < 0 else SHOULDER_R
            armpit = (edge - sign * -10, SHOULDER_Y + 80)
            sleeve = [(edge, SHOULDER_Y), (edge + sign * -dx, SHOULDER_Y + dy),
                      (armpit[0] + sign * -dx, armpit[1] + dy - 40), armpit]
            md.polygon(sleeve, fill=255)
            sleeves.append(sleeve)
    # neckline cut-out
    collar = state.get("collar", "none")
    if collar in ("v_neck",):
        md.polygon([(262, SHOULDER_Y - 2), (338, SHOULDER_Y - 2), (CX, SHOULDER_Y + 85)], fill=0)
    elif collar == "round_neck":
        md.ellipse((258, SHOULDER_Y - 30, 342, SHOULDER_Y + 52), fill=0)  # open, scooped neckline
    elif collar == "none":
        md.ellipse((278, SHOULDER_Y - 22, 322, SHOULDER_Y + 6), fill=0)  # plain high neck opening
    elif collar == "shawl":
        md.ellipse((268, SHOULDER_Y - 28, 332, SHOULDER_Y + 28), fill=0)
    else:
        md.ellipse((272, SHOULDER_Y - 22, 328, SHOULDER_Y + 18), fill=0)

    # fabric fill according to motif placement
    placement = state.get("motif_placement", "all_over")
    flat = Image.new("RGB", (W, H), _mean(texture))
    tiled = _tiled(texture)
    fill = tiled
    if placement == "center_front":
        fill = flat.copy()
        fill.paste(tiled.crop((255, 0, 345, H)), (255, 0))
    elif placement == "left_chest":
        fill = flat.copy()
        patch = Image.new("L", (W, H), 0)
        ImageDraw.Draw(patch).ellipse((305, SHOULDER_Y + 40, 395, SHOULDER_Y + 130), fill=255)
        fill.paste(tiled, (0, 0), patch)
    elif placement == "hem_border":
        fill = flat.copy()
        fill.paste(tiled.crop((0, hem_y - 80, W, hem_y)), (0, hem_y - 80))
    out.drawn.append(f"motif_placement={placement}")
    out.image.paste(fill, (0, 0), mask)

    d = ImageDraw.Draw(out.image)
    d.polygon(torso, outline=OUTLINE, width=3)
    for sleeve in sleeves:
        d.polygon(sleeve, outline=OUTLINE, width=3)
    _collar(d, collar, out)
    _pockets(d, state.get("pockets", "none"), hem_y, out)
    _closure_and_buttons(d, state, hem_y, out)
    _trim(d, state.get("trim", "none"), hem_y, out)
    if "hem_length_delta_cm" in state:
        out.drawn.append(f"hem_length_delta_cm={state['hem_length_delta_cm']}")
    if "sleeve_length_delta_cm" in state and sleeve_kind:
        out.drawn.append(f"sleeve_length_delta_cm={state['sleeve_length_delta_cm']}")
    for name in state:
        if name not in HANDLED:
            out.warnings.append(f"Detail '{name}' belum digambar pada pratinjau ini")
    return out


def _collar(d, collar: str, out: Rendered) -> None:
    if collar == "mandarin":
        d.rectangle((268, SHOULDER_Y - 30, 332, SHOULDER_Y + 2), outline=OUTLINE, width=3)
    elif collar == "classic":
        d.polygon([(268, SHOULDER_Y - 6), (CX, SHOULDER_Y + 4), (252, SHOULDER_Y + 46)],
                  outline=OUTLINE, width=3)
        d.polygon([(332, SHOULDER_Y - 6), (CX, SHOULDER_Y + 4), (348, SHOULDER_Y + 46)],
                  outline=OUTLINE, width=3)
    elif collar == "shawl":
        d.line([(262, SHOULDER_Y - 8), (CX, SHOULDER_Y + 120), (338, SHOULDER_Y - 8)],
               fill=OUTLINE, width=3)
    elif collar in ("v_neck", "round_neck"):
        pass  # shape already cut from the silhouette
    out.drawn.append(f"collar={collar}")


def _pockets(d, pockets: str, hem_y: int, out: Rendered) -> None:
    def rect(x1, y1, x2, y2):
        d.rectangle((x1, y1, x2, y2), outline=OUTLINE, width=3)

    if pockets == "left_chest_single":
        rect(335, SHOULDER_Y + 70, 390, SHOULDER_Y + 125)
    elif pockets == "double_chest":
        rect(335, SHOULDER_Y + 70, 390, SHOULDER_Y + 125)
        rect(210, SHOULDER_Y + 70, 265, SHOULDER_Y + 125)
    elif pockets == "side_double":
        for x in (214, 340):
            rect(x, hem_y - 120, x + 46, hem_y - 60)
    elif pockets == "double_welt":
        for x in (222, 336):
            d.line([(x, hem_y - 95), (x + 40, hem_y - 80)], fill=OUTLINE, width=4)
    out.drawn.append(f"pockets={pockets}")


def _closure_and_buttons(d, state: dict, hem_y: int, out: Rendered) -> None:
    closure = state.get("closure")
    has_placket = closure in (None, "buttons_front") and state.get("collar") != "none" or \
        closure == "buttons_front"
    if closure == "side_zip":
        d.line([(396, SHOULDER_Y + 90), (392, hem_y)], fill=OUTLINE, width=3)
    elif closure == "open_front":
        d.line([(CX - 4, SHOULDER_Y), (CX - 4, hem_y)], fill=OUTLINE, width=3)
        d.line([(CX + 4, SHOULDER_Y), (CX + 4, hem_y)], fill=OUTLINE, width=3)
    elif closure == "tie_front":
        d.line([(CX, SHOULDER_Y + 120), (CX - 30, SHOULDER_Y + 210)], fill=OUTLINE, width=4)
        d.line([(CX, SHOULDER_Y + 120), (CX + 30, SHOULDER_Y + 215)], fill=OUTLINE, width=4)
    elif has_placket and "buttons" in state:
        d.line([(CX, SHOULDER_Y + 20), (CX, hem_y)], fill=OUTLINE, width=2)
        color = BUTTON_COLORS.get(state["buttons"], (200, 200, 200))
        y = SHOULDER_Y + 50
        while y < hem_y - 20:
            d.ellipse((CX - 7, y - 7, CX + 7, y + 7), fill=color + (255,), outline=OUTLINE, width=2)
            y += 55
        out.drawn.append(f"buttons={state['buttons']}")
    if closure:
        out.drawn.append(f"closure={closure}")


def _trim(d, trim: str, hem_y: int, out: Rendered) -> None:
    if trim in ("fringe_short", "fringe_long"):
        length = 22 if trim == "fringe_short" else 44
        for x in range(SHOULDER_L + 12, SHOULDER_R - 8, 9):
            d.line([(x, hem_y), (x, hem_y + length)], fill=OUTLINE, width=2)
        out.drawn.append(f"trim={trim}")


def to_png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def compose_on_body(photo: Image.Image, pose: PoseResult, garment: Image.Image) -> Image.Image:
    """Place the garment illustration over the person using shoulder landmarks (visual reference only)."""
    photo = ImageOps.exif_transpose(photo).convert("RGBA")
    photo.thumbnail((1280, 1280))
    m = pose.landmarks
    ls = (m["l_shoulder"].x * photo.width, m["l_shoulder"].y * photo.height)
    rs = (m["r_shoulder"].x * photo.width, m["r_shoulder"].y * photo.height)
    span = ((ls[0] - rs[0]) ** 2 + (ls[1] - rs[1]) ** 2) ** 0.5
    scale = span * 1.25 / (SHOULDER_R - SHOULDER_L)
    resized = garment.resize((max(1, int(W * scale)), max(1, int(H * scale))))
    alpha = resized.getchannel("A").point(lambda a: int(a * 0.92))
    resized.putalpha(alpha)
    mid = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
    pos = (int(mid[0] - CX * scale), int(mid[1] - SHOULDER_Y * scale))
    canvas = photo.copy()
    canvas.alpha_composite(resized, dest=(max(0, pos[0]), max(0, pos[1])),
                           source=(max(0, -pos[0]), max(0, -pos[1])))
    return canvas.convert("RGB")
