"""Turn a free-text request into candidate structured changes.

Interpreters only propose; `customization.propose` validates every candidate against the template
schema on the server. Output shape (all interpreters):
    {"changes": [{"field", "value"}],
     "unsupported": [{"text", "reason", "alternatives": [...]}],
     "clarifications": [{"field", "text", "question", "choices": [...]}]}
"""
import json
import re
from collections.abc import Callable

from app.core.config import settings


class InterpretationFailed(Exception):
    pass


_SPLIT = re.compile(r"[;,\n]|\.\s|\.$|\bdan\b|\band\b|\bserta\b|\bplus\b|\blalu\b|\bkemudian\b|\bthen\b")
_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:cm|centimeter|sentimeter)")
_SHORTEN = re.compile(r"pendek|potong|kurangi|kurang|shorten|shorter|cut|reduce|minus|\bkecil")
_LENGTHEN = re.compile(r"panjangkan|perpanjang|tambah(?:kan)? panjang|lengthen|longer|extend|tambah(?:kan)? \d")
_NEGATE = re.compile(r"tanpa|tidak (?:pakai|ada|usah)|hapus|hilangkan|\bno\b|without|remove|polos saja")
_STYLE_UNSUPPORTED = re.compile(
    r"gaun|dress|celana|\brok\b|skirt|bordir|sulam|embroider|payet|sequin|bulu|\bfur\b|ubah (?:model|bentuk)"
    r"|siluet|silhouette|crop|oversize|lengan panjang|long sleeve|lengan balon|puff|ruffle|kerut")

_TOPICS = {
    "pockets": re.compile(r"saku|kantong|pocket"),
    "buttons": re.compile(r"kancing|button"),
    "collar": re.compile(r"kerah|collar|leher|neckline|\bneck"),
    "closure": re.compile(r"resleting|ritsleting|\bzip|closure|penutup|tali depan|terbuka|\bopen front"),
    "trim": re.compile(r"rumbai|fringe|jumbai|tassel"),
    "motif_placement": re.compile(r"motif|corak|pola"),
}


def _alt(defn: dict, field: str) -> list[str]:
    spec = defn["options"].get(field)
    return list(spec["values"]) if spec and spec["type"] == "enum" else []


def _has(defn: dict, field: str) -> bool:
    return field in defn["options"]


class RuleBasedInterpreter:
    name = "rules"

    def interpret(self, prompt: str, defn: dict, state: dict) -> dict:
        out = {"changes": [], "unsupported": [], "clarifications": []}
        clauses = [c.strip() for c in _SPLIT.split(prompt.lower()) if c and c.strip()]
        for clause in clauses:
            self._clause(clause, defn, state, out)
        self._resolve_conflicts(out)
        return out

    # -- one clause ------------------------------------------------------------------------
    def _clause(self, c: str, defn: dict, state: dict, out: dict) -> None:
        def unsupported(reason, alternatives=None):
            out["unsupported"].append({"text": c, "reason": reason, "alternatives": alternatives or []})

        def clarify(field, question, choices):
            out["clarifications"].append({"field": field, "text": c, "question": question,
                                          "choices": choices})

        def change(field, value):
            out["changes"].append({"field": field, "value": value})

        if _STYLE_UNSUPPORTED.search(c):
            return unsupported("Perubahan siluet, bahan tambahan, atau jenis pakaian tidak didukung "
                               "pada template ini", sorted(defn["options"]))

        num = _NUM.search(c)
        if num and not any(t.search(c) for k, t in _TOPICS.items() if k != "motif_placement"):
            return self._length(c, num, defn, state, out)

        for field, pattern in _TOPICS.items():
            if pattern.search(c):
                return getattr(self, f"_{field}")(c, defn, unsupported, clarify, change)
        unsupported("Permintaan tidak dikenali sebagai opsi yang didukung", sorted(defn["options"]))

    # -- lengths ---------------------------------------------------------------------------
    def _length(self, c, num, defn, state, out) -> None:
        amount = float(num.group(1).replace(",", "."))
        if _SHORTEN.search(c) and not _LENGTHEN.search(c):
            sign = -1
        elif _LENGTHEN.search(c):
            sign = 1
        else:
            out["unsupported"].append({"text": c, "reason": "Arah perubahan panjang tidak jelas",
                                       "alternatives": []})
            return
        sleeve = re.search(r"lengan|sleeve", c)
        hem = re.search(r"hem|bawah|ujung|panjang (?:baju|badan|kemeja|blouse|tunik|rompi|outer)"
                        r"|body length|baju|kemeja|blouse|tunik|rompi|outer|garment", c)
        if sleeve:
            field = "sleeve_length_delta_cm"
        elif hem:
            field = "hem_length_delta_cm"
        else:
            choices = [f for f in ("hem_length_delta_cm", "sleeve_length_delta_cm") if _has(defn, f)]
            out["clarifications"].append({
                "field": "length", "text": c, "choices": choices,
                "question": "Bagian mana yang ingin diubah panjangnya?",
                "direction": sign * amount})
            return
        if not _has(defn, field):
            out["unsupported"].append({"text": c, "reason": f"Template ini tidak memiliki opsi '{field}'",
                                       "alternatives": sorted(defn["options"])})
            return
        base = state.get(field, 0) or 0
        out["changes"].append({"field": field, "value": base + sign * amount})

    # -- topics ----------------------------------------------------------------------------
    def _pockets(self, c, defn, unsupported, clarify, change) -> None:
        if not _has(defn, "pockets"):
            return unsupported("Template ini tidak memiliki opsi saku", [])
        values = _alt(defn, "pockets")
        if _NEGATE.search(c):
            return change("pockets", "none")
        double = re.search(r"dua|double|2 ", c)
        guess = None
        if re.search(r"samping|side", c):
            guess = "side_double"
        elif re.search(r"dalam|welt", c):
            guess = "double_welt"
        elif double and re.search(r"dada|chest", c):
            guess = "double_chest"
        elif re.search(r"dada kiri|kiri|left", c):
            guess = "left_chest_single"
        if guess is None:
            return clarify("pockets", "Jenis saku mana yang Anda inginkan?",
                           [v for v in values if v != "none"])
        if guess not in values:
            return unsupported(f"Jenis saku '{guess}' tidak tersedia pada template ini", values)
        change("pockets", guess)

    def _buttons(self, c, defn, unsupported, clarify, change) -> None:
        if not _has(defn, "buttons"):
            return unsupported("Template ini tidak memiliki opsi kancing", [])
        values = _alt(defn, "buttons")
        if re.search(r"emas|gold|perak|silver|kristal|crystal|berlian|mutiara", c):
            return unsupported("Bahan kancing tersebut tidak tersedia", values)
        if re.search(r"kayu|wood", c):
            return change("buttons", "wood_option_01")
        if re.search(r"kerang|shell", c):
            return change("buttons", "shell_option_01")
        if re.search(r"polos|plain|biasa", c):
            return change("buttons", "plain_01")
        clarify("buttons", "Bahan kancing apa yang Anda inginkan?", values)

    def _collar(self, c, defn, unsupported, clarify, change) -> None:
        if not _has(defn, "collar"):
            return unsupported("Template ini tidak memiliki opsi kerah/leher", [])
        values = _alt(defn, "collar")
        if re.search(r"bulu|fur", c):
            return unsupported("Kerah bulu tidak didukung", values)
        guess = None
        if _NEGATE.search(c):
            guess = "none"
        elif "mandarin" in c:
            guess = "mandarin"
        elif re.search(r"klasik|classic|biasa", c):
            guess = "classic"
        elif "shawl" in c:
            guess = "shawl"
        elif re.search(r"\bv\b|v-neck|leher v", c):
            guess = "v_neck"
        elif re.search(r"bulat|round", c):
            guess = "round_neck"
        if guess is None:
            return clarify("collar", "Model kerah/leher apa yang Anda inginkan?", values)
        if guess not in values:
            return unsupported(f"Model '{guess}' tidak tersedia pada template ini", values)
        change("collar", guess)

    def _closure(self, c, defn, unsupported, clarify, change) -> None:
        if not _has(defn, "closure"):
            return unsupported("Template ini tidak memiliki opsi penutup depan", [])
        values = _alt(defn, "closure")
        guess = None
        if re.search(r"resleting|ritsleting|zip", c):
            guess = "side_zip"
        elif re.search(r"tali|tie", c):
            guess = "tie_front"
        elif re.search(r"terbuka|open", c):
            guess = "open_front"
        if guess is None:
            return clarify("closure", "Jenis penutup apa yang Anda inginkan?", values)
        if guess not in values:
            return unsupported(f"Penutup '{guess}' tidak tersedia pada template ini", values)
        change("closure", guess)

    def _trim(self, c, defn, unsupported, clarify, change) -> None:
        if not _has(defn, "trim"):
            return unsupported("Template ini tidak mendukung rumbai/trim", [])
        if _NEGATE.search(c):
            return change("trim", "none")
        if re.search(r"panjang|long", c):
            return change("trim", "fringe_long")
        if re.search(r"pendek|short", c):
            return change("trim", "fringe_short")
        clarify("trim", "Panjang rumbai yang Anda inginkan?", ["fringe_short", "fringe_long"])

    def _motif_placement(self, c, defn, unsupported, clarify, change) -> None:
        if not _has(defn, "motif_placement"):
            return unsupported("Template ini tidak memiliki opsi penempatan motif", [])
        values = _alt(defn, "motif_placement")
        if re.search(r"dada kiri|left chest", c):
            return change("motif_placement", "left_chest")
        if re.search(r"seluruh|all over|menyeluruh|merata|penuh", c):
            return change("motif_placement", "all_over")
        if re.search(r"bawah|hem|tepi|border", c):
            return change("motif_placement", "hem_border")
        if re.search(r"tengah|center|depan", c):
            return change("motif_placement", "center_front")
        clarify("motif_placement", "Di bagian mana motif diletakkan?", values)

    # -- conflicts -------------------------------------------------------------------------
    @staticmethod
    def _resolve_conflicts(out: dict) -> None:
        seen: dict[str, dict] = {}
        for ch in list(out["changes"]):
            prior = seen.get(ch["field"])
            if prior is None:
                seen[ch["field"]] = ch
            elif prior["value"] != ch["value"]:
                out["changes"] = [x for x in out["changes"] if x["field"] != ch["field"]]
                out["clarifications"].append({
                    "field": ch["field"], "text": "permintaan bertentangan",
                    "question": f"Permintaan untuk '{ch['field']}' saling bertentangan; pilih satu.",
                    "choices": [prior["value"], ch["value"]]})
            else:
                out["changes"].remove(ch)


class LLMInterpreter:
    """Asks an OpenAI-compatible chat model for the same structure; the server still validates it."""

    name = "llm"

    def __init__(self, transport: Callable[[list[dict]], str]):
        self.transport = transport

    def interpret(self, prompt: str, defn: dict, state: dict) -> dict:
        system = ("Terjemahkan permintaan pembeli menjadi perubahan opsi garmen. Balas HANYA JSON: "
                  '{"changes":[{"field":..,"value":..}],"unsupported":[{"text":..,"reason":..,'
                  '"alternatives":[..]}],"clarifications":[{"field":..,"text":..,"question":..,'
                  '"choices":[..]}]}. Hanya gunakan field dan nilai dari skema. Nilai numerik '
                  "adalah nilai AKHIR absolut (bukan selisih) dalam cm. Jangan mengarang opsi.")
        user = json.dumps({"schema": defn["options"], "current_state": state, "request": prompt})
        try:
            raw = self.transport([{"role": "system", "content": system},
                                  {"role": "user", "content": user}])
            data = json.loads(raw)
            return {"changes": list(data.get("changes", [])),
                    "unsupported": list(data.get("unsupported", [])),
                    "clarifications": list(data.get("clarifications", []))}
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise InterpretationFailed(str(exc)) from exc


def http_transport(messages: list[dict]) -> str:
    """Real transport for the LLMInterpreter using the configured OpenAI-compatible provider."""
    import urllib.request

    bases = {"openai": ("https://api.openai.com/v1", settings.openai_api_key),
             "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key),
             "ollama": ("http://localhost:11434/v1", "")}
    base, key = bases[settings.llm_provider]
    body = json.dumps({"model": settings.llm_model, "messages": messages, "temperature": 0,
                       "response_format": {"type": "json_object"}}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/chat/completions", data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def get_interpreters() -> list:
    """Interpreters to try in order; rules are always the final, offline fallback."""
    chain = []
    if settings.prompt_interpreter == "llm":
        chain.append(LLMInterpreter(http_transport))
    chain.append(RuleBasedInterpreter())
    return chain
