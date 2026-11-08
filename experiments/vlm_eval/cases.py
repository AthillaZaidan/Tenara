"""The 13 test photos with known origin, shared by the scan experiments.

Sikka photos are GI-registered Sikka ikat motifs (Mendeley); KITLV titles say "uit Soemba"; the songket
is catalogued as Palembang; the rest are museum pieces with recorded provenance. Region counts as
right if any keyword appears. testset/assets is downloaded and git-ignored (credits in credits.json).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIKKA = ROOT / "data/tenun_datasets/mendeley_sikka_v3/extracted/sikka_motif_512"
IMG = ROOT / "web/public/img"
TEST = ROOT / "experiments/vlm_eval/testset/assets"  # downloaded, credited in credits.json, git-ignored
# Known origins: Sikka photos are GI-registered Sikka ikat motifs; KITLV titles say "uit Soemba";
# the songket is catalogued as Palembang. Region counts as right if any keyword appears.
CASES = [
    ("sikka_naga_lalan", SIKKA / "naga_lalan/nagalalan_indoor_morning_007_png.rf.ebcd3e7134b1656e52d687797d05fb19.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_merak", SIKKA / "merak/merak_outdoor_morning_164_png.rf.9be658daa3c707fb11c25e05ceb34726.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sumba_kitlv_5636", IMG / "ikat-1.jpg", "ikat", ["sumba"]),
    ("sumba_laoe_komboe", IMG / "ikat-3.jpg", "ikat", ["sumba"]),
    ("songket_palembang", IMG / "songket.jpg", "songket", ["palembang", "sumatera selatan", "south sumatra"]),
    # more Sikka motif classes (GI-registered), and museum pieces with recorded provenance
    ("sikka_dala_mawarani", SIKKA / "dala_mawarani/dalamawarani_outdoor_morning_046_png.rf.20fdf267cbaa3424f63c7851c6021e38.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_manu_hutu", SIKKA / "manu_hutu/manu_hutu_outdoor_morning_012_png.rf.711707d8df8dd26c9ab531a3781cd371.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_rempe_sikka", SIKKA / "rempe_sikka/rempe_sikka_outdoor_morning_074_png.rf.89359e0adb6a273d21fcdc8e1c5db538.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_sese_weor", SIKKA / "sese_weor/sese_weor_outdoor_morning_002_png.rf.a611a3c480cd938ced3dc45efe3e61dc.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("tapis_lampung_met", TEST / "woman-s-ceremonial-skirt-tapis-met-dp145517.jpg", "other", ["lampung", "tapis"]),
    ("geringsing_honolulu", TEST / "geringsing-selendang-from-bali-honolulu-museum-of.jpg", "ikat",
     ["gringsing", "geringsing", "tenganan"]),
    ("kalumpang_kitlv", TEST / "ikatweefsel-afkomsting-uit-galoempang-in-de-toradjalanden.jpg", "ikat",
     ["kalumpang", "sekomandi", "mamuju"]),
    ("timor_heirloom", TEST / "heirloom-ikat-textile-from-timor.jpg", "ikat", ["timor", "amarasi", "insana"]),
]
