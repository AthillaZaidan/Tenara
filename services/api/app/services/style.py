"""Free garment style on top of a template: what the buyer wants the cut to look like, in words.

A style is a list of short requests, each about one part of the garment:
    [{"part": "sleeves", "text": "lengan balon mengerut di pergelangan", "en": "puff sleeves gathered at the wrist"}]
`text` (Indonesian) is what the buyer and the tailor read; `en` (optional) is what the image model reads.

The template stays the base block (measurements, fabric estimate, tailor price). A style request is part of
the design the tailor validates in the quote; until then it is a request, not accepted production scope.

What a style may NOT change is the fabric: tenun is woven, so its colours and motifs are what the merchant
ships. Requests that recolour it, add motifs or decoration, swap the garment type, or would make an indecent
or branded image are refused here, whoever proposed them (rules, LLM or a hand-made request).
"""
import re

PARTS = ("silhouette", "sleeves", "neckline", "body", "hem", "slit", "detail")
MAX_ITEMS = 8
MAX_CHARS = 160

# reason shown to the buyer, and what to say instead
REFUSALS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"warna|\bwarnai|\bcolou?r|\bdye|celup|\bcat\b|merah|biru|hijau|kuning|ungu|pink"),
     "Warna kain tenun tidak bisa diubah; warnanya mengikuti kain asli yang dikirim penjual"),
    (re.compile(r"\bmotif (?:baru|lain|bunga|naga)|tambah(?:kan)? motif|ganti motif|\bprint\b|sablon|lukis|bordir|"
                r"sulam|embroider|payet|sequin|manik|\bbead"),
     ("Motif dan hiasan baru tidak bisa ditambahkan; yang dipakai hanya motif tenunan kain ini (atur letaknya "
      "lewat peta motif)")),
    (re.compile(r"\bgaun\b|\bdress\b|celana|\bpants|trouser|\brok\b|\bskirt|jumpsuit|hoodie|jaket kulit"),
     "Jenis pakaian tidak bisa diganti lewat gaya; pilih model lain di langkah Pilih model"),
    (re.compile(r"transparan|tembus pandang|see.?through|telanjang|\bnude|seksi|\bsexy|belahan dada|lingerie"),
     "Permintaan ini tidak bisa dibuat"),
    (re.compile(r"\blogo\b|\bmerek\b|\bbrand\b|gucci|louis vuitton|chanel|prada|dior|nike|adidas|zara|uniqlo"),
     "Logo atau tiruan merek tidak bisa dibuat"),
    (re.compile(r"\bbulu\b|\bfur\b|kulit asli|leather|beludru|velvet|renda|\blace\b|tulle|kain lain"),
     "Bahan tambahan di luar kain ini tidak didukung; satu pesanan memakai satu kain"),
]

# Indonesian words that make a clause a style request (the rules fallback; the LLM decides on its own)
STYLE_WORDS = re.compile(
    r"oversize|longgar|\bloose|boxy|siluet|silhouette|\bslim\b|ketat|\bfit\b|pas badan|crop|\ba-line|"
    r"lengan (?:panjang|pendek|balon|lonceng|kelelawar|kimono|sabrina|lebar|sempit|3/4|tiga perempat|"
    r"mengembang|kerut|lipit)|puff|bishop|bell sleeve|batwing|raglan|manset|\bcuff|"
    r"belahan|\bslit\b|asimetris|asymmetric|peplum|lipit|pleat|kerut|ruffle|draperi|drape|"
    r"panjang (?:selutut|semata kaki|sepaha|sebetis)|selutut|semata kaki|sepaha|sebetis|"
    r"ikat pinggang|\bsabuk\b|\bbelt\b|\btali\b|obi|kerah (?:sanghai|shanghai|tinggi|lebar|besar|kecil|tegak)|"
    r"\bhem (?:melengkung|bulat|lurus)|melengkung|bagian bawah (?:melebar|mengembang)|melebar|mengembang|flare"
)
PART_WORDS = [
    ("slit", re.compile(r"belahan|\bslit\b")),
    ("sleeves", re.compile(r"lengan|sleeve|manset|\bcuff|puff|bishop|batwing|raglan")),
    ("neckline", re.compile(r"kerah|leher|neck|collar")),
    ("hem", re.compile(r"bawah|\bhem\b|asimetris|asymmetric|selutut|semata kaki|sepaha|sebetis|melengkung|flare")),
    ("silhouette", re.compile(r"oversize|longgar|\bloose|boxy|siluet|silhouette|\bslim\b|ketat|\bfit\b|pas badan|"
                              r"crop|\ba-line|peplum")),
    ("body", re.compile(r"ikat pinggang|\bsabuk|\bbelt|\btali|obi|lipit|pleat|kerut|draperi|drape")),
]


def refusal(text: str) -> str | None:
    lower = text.lower()
    return next((reason for pattern, reason in REFUSALS if pattern.search(lower)), None)


def guess_part(text: str) -> str:
    lower = text.lower()
    return next((part for part, pattern in PART_WORDS if pattern.search(lower)), "detail")


def check(value) -> list[dict]:
    """The normalised style list, or ValueError(reason). Server-side source of truth for every proposer."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("Gaya harus berupa daftar permintaan")  # noqa: TRY004 (callers report ValueError)
    if len(value) > MAX_ITEMS:
        raise ValueError(f"Maksimal {MAX_ITEMS} permintaan gaya; gabungkan atau hapus sebagian")
    out, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Tiap permintaan gaya harus berisi bagian dan teks")  # noqa: TRY004 (as above)
        part = item.get("part") if item.get("part") in PARTS else "detail"
        text = " ".join(str(item.get("text") or "").split())
        en = " ".join(str(item.get("en") or "").split())
        if len(text) < 3:
            raise ValueError("Permintaan gaya terlalu pendek")
        if len(text) > MAX_CHARS or len(en) > MAX_CHARS:
            raise ValueError(f"Permintaan gaya maksimal {MAX_CHARS} karakter")
        reason = refusal(text) or (refusal(en) if en else None)
        if reason:
            raise ValueError(f"'{text}': {reason}")
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append({"part": part, "text": text, **({"en": en} if en else {})})
    return out
