"""
WhatTheChip — Engine de Classificação de Chips
===============================================
Classifica um Part Number em três camadas:

  1. Banco exato (KnownPart enriched)  → resultado completo e verificado
  2. Gramática da família (ChipFamily) → decodificação posicional do PN
       └→ complementado por Gemini se campos essenciais estiverem vazios
  3. Gemini puro (prefix desconhecido) → fallback IA com Google Search grounding
  4. Fuzzy matching                    → sugestões para erros de digitação

Double-check:
    Quando o banco E a gramática têm resultados, eles são comparados.
    Divergência de capacidade é sinalizada como possível chip remarked.
"""

import json
import os
import re
import urllib.request
import urllib.error

from .models import Brand, ChipFamily, DecodeMap, KnownPart, SearchLog, UnknownChip


# ── Fuzzy matching ─────────────────────────────────────────────────────────────

COMMON_CONFUSIONS = [
    ("O", "0"), ("I", "1"), ("B", "8"), ("V", "Y"), ("Z", "2"), ("S", "5"),
]


def _edit_distance(a: str, b: str) -> int:
    """Distância de Levenshtein."""
    if len(a) > len(b):
        a, b = b, a
    distances = range(len(a) + 1)
    for c2 in b:
        distances_ = [distances[0] + 1]
        for i, c1 in enumerate(a):
            distances_.append(
                min(distances_[-1] + 1, distances[i + 1] + 1, distances[i] + (c1 != c2))
            )
        distances = distances_
    return distances[-1]


def _fuzzy_candidates(pn: str, threshold: int = 2) -> list:
    """Retorna KnownParts parecidos por distância de edição."""
    all_parts = KnownPart.objects.filter(status="enriched").values_list("part_number", flat=True)
    matches = []
    for candidate in all_parts:
        if abs(len(candidate) - len(pn)) > threshold:
            continue
        dist = _edit_distance(pn, candidate)
        if dist <= threshold:
            matches.append((dist, candidate))
    matches.sort()
    return [KnownPart.objects.get(part_number=c) for _, c in matches[:5]]


# ── Mapa de decodificação ──────────────────────────────────────────────────────

def _load_decode_map(map_name: str) -> dict:
    rows = DecodeMap.objects.filter(map_name=map_name).values("char_key", "val_primary", "val_secondary")
    return {r["char_key"]: (r["val_primary"], r["val_secondary"]) for r in rows}


# ── Match de família ──────────────────────────────────────────────────────────

def _match_family(pn: str):
    """Retorna ChipFamily com o prefixo mais longo que bater no PN."""
    families = ChipFamily.objects.filter(active=True).order_by("priority", "-prefix")
    for fam in families:
        if pn.startswith(fam.prefix):
            return fam
    return None


# ── URL da documentação ────────────────────────────────────────────────────────

def _doc_url(family) -> str | None:
    """Retorna a URL da página de documentação ligada à família, se existir."""
    if family and family.doc_page_id:
        try:
            return family.doc_page.get_absolute_url()
        except Exception:
            pass
    return None


# ── eMCP: tipo RAM pela 3ª letra ───────────────────────────────────────────────

EMCP_RAM_TYPES = {
    "V": "LPDDR2",
    "K": "LPDDR2 (legado)",
    "J": "LPDDR (legado)",
    "S": "LPDDR (legado)",
    "Z": "LPDDR2 / LPDDR (?)",
    "Y": "LPDDR2",
    "Q": "LPDDR3",
    "R": "LPDDR3",
    "G": "LPDDR3",
    "F": "LPDDR4 / LPDDR4X",
    "N": "LPDDR4X",
    "D": "LPDDR4X",
    "L": "LPDDR5",
}


# ── Resultado base da família ──────────────────────────────────────────────────

def _result_from_family(pn: str, fam) -> dict:
    """Decodifica o PN usando as regras da família. Retorna resultado parcial."""
    r = {
        "pn":            pn,
        "known":         True,
        "known_exact":   False,
        "chip_type":     fam.chip_type,
        "subtype":       fam.subtype,
        "interface":     fam.interface,
        "family_prefix": fam.prefix,
        "brand":         fam.brand.name,
        "is_emcp":       fam.is_emcp,
        "tip":           fam.tip or "",
        "reasoning":     json.loads(fam.reasoning) if fam.reasoning else [],
        "doc_url":       _doc_url(fam),
        "capacity":      None,
        "dram_density":  None,
        "emcp_ram":      None,
        "emcp_nand":     None,
        "emcp_device":   None,
        "emcp_source":   None,
        "device":        None,
        "confidence":    "estimated",
        "source_url":    None,
        "from_web":      False,
        "suffix_note":   None,
        "remarked_flag": False,
        "fuzzy_suggestions": [],
    }

    # ── Capacidade eMMC / UFS ────────────────────────────────────────────────
    if fam.decode_cap_pos is not None and fam.decode_cap_map and not fam.is_emcp:
        cap_map = _load_decode_map(fam.decode_cap_map)
        pos = fam.decode_cap_pos
        if len(pn) > pos:
            entry = cap_map.get(pn[pos])
            if entry:
                r["capacity"] = entry[0]

    # ── Geração eMMC ─────────────────────────────────────────────────────────
    if fam.decode_gen_pos is not None and fam.decode_gen_map:
        gen_map = _load_decode_map(fam.decode_gen_map)
        pos = fam.decode_gen_pos
        if len(pn) > pos:
            entry = gen_map.get(pn[pos])
            if entry:
                r["interface"] = entry[0]

    # ── Densidade DRAM ───────────────────────────────────────────────────────
    if fam.decode_density_type and not fam.is_emcp:
        dtype = fam.decode_density_type
        density_map = _load_decode_map("DRAM_PC" if dtype == "pc" else "DRAM_MOBILE")
        if dtype == "pc" and len(pn) >= 5:
            code = pn[3:5]
            entry = density_map.get(code)
            if entry and entry[0]:
                conf = "✓" if code in ("4G", "8G", "16", "32", "64") else "~"
                r["dram_density"] = f"{entry[0]} = {entry[1]} por die [{conf}]"
            else:
                r["dram_density"] = f"Código '{code}' não mapeado — consultar datasheet"
        elif dtype == "mobile" and len(pn) >= 4:
            code = pn[3]
            entry = density_map.get(code)
            if entry and entry[0]:
                conf = "✓" if code in ("4", "8", "G", "H") else "~"
                r["dram_density"] = f"{entry[0]} = {entry[1]} por die [{conf}]"
            else:
                r["dram_density"] = f"Código '{code}' não mapeado — consultar datasheet"

    # ── eMCP: tipo RAM pela 3ª letra ─────────────────────────────────────────
    if fam.is_emcp:
        ram_char = pn[2] if len(pn) > 2 else "?"
        r["emcp_ram"]  = EMCP_RAM_TYPES.get(ram_char, f"tipo '{ram_char}' — consultar datasheet")
        r["emcp_nand"] = "eMMC"
        r["emcp_source"] = "parcial (gramática)"

    # ── Sufixo ───────────────────────────────────────────────────────────────
    if fam.suffix_rules:
        sfx = json.loads(fam.suffix_rules)
        for s, data in sfx.items():
            if pn.endswith(s):
                r["suffix_note"] = data.get("note", "")
                break
        else:
            r["suffix_note"] = f"Sufixo não mapeado — verificar: {list(sfx.keys())}"

    return r


def _result_from_known(pn: str, known, fam) -> dict:
    """Sobrepõe resultado da família com dados confirmados do KnownPart."""
    r = _result_from_family(pn, fam)

    if fam.is_emcp:
        r["emcp_ram"]    = known.emcp_ram  or r["emcp_ram"]
        r["emcp_nand"]   = known.emcp_nand or r["emcp_nand"]
        r["emcp_device"] = known.device    or None
        r["emcp_source"] = known.confidence
        r["source_url"]  = known.source_url
    else:
        if known.capacity:
            r["capacity"] = known.capacity
        if known.density_gbit:
            r["dram_density"] = f"{known.density_gbit} = {known.density_gb} por die [✓]"
        if known.device:
            r["device"] = known.device

    r["confidence"]  = known.confidence
    r["source_url"]  = known.source_url or r["source_url"]
    r["known_exact"] = True
    return r


# ── Double-check: detecta possível remarked ───────────────────────────────────

_CAP_RE = re.compile(r"(\d+)\s*([GMK])B", re.I)


def _extract_gib(text: str) -> float | None:
    """Extrai capacidade em GB a partir de string como '4GB', '512MB'."""
    if not text:
        return None
    m = _CAP_RE.search(text)
    if not m:
        return None
    val, unit = float(m.group(1)), m.group(2).upper()
    if unit == "K":
        return val / 1024 / 1024
    if unit == "M":
        return val / 1024
    return val  # GB


def _check_remarked(grammar_result: dict, db_result: dict) -> bool:
    """
    Retorna True se gramática e banco divergem em capacidade — sinal de possível remarked.
    Só compara campos preenchidos em ambos.
    """
    for field in ("capacity", "dram_density"):
        g_val = grammar_result.get(field)
        d_val = db_result.get(field)
        if not g_val or not d_val:
            continue
        g_cap = _extract_gib(str(g_val))
        d_cap = _extract_gib(str(d_val))
        if g_cap and d_cap and abs(g_cap - d_cap) > 0.1:
            return True
    return False


# ── Gemini fallback ────────────────────────────────────────────────────────────

GEMINI_PROMPT = """Você é especialista em chips de memória e semicondutores para dispositivos eletrônicos.
Pesquise o Part Number abaixo — use o Google Search se disponível.

Part Number: {pn}
{family_hint}
⚠ REGRA CRÍTICA PARA eMCP/uMCP:
Identificar apenas que o chip É um eMCP NÃO É SUFICIENTE.
Para chips eMCP e uMCP, os campos "ram" e "nand" são OBRIGATÓRIOS com valores reais (ex: "LPDDR4X 4GB", "eMMC 5.1 64GB").
Se você encontrar que é um eMCP mas não tem os valores de RAM e NAND, CONTINUE pesquisando.
Busque em: preduo.com, censtry.com, serviceemmc.com, jotrin.com, wolfchip.com, glochip.com

== GUIA DE DECODIFICAÇÃO DE PART NUMBERS ==

SAMSUNG eMCP (KMR, KMQ, KMD, KMF, KMK, KMG, KM3, KM5, KM8...):
  Prefixo KM = eMCP Samsung (NAND eMMC + LPDDR RAM no mesmo package)
  Prefixo KLM = eMMC Samsung (standalone, sem RAM)
  Para KLM: Pos 3 = capacidade NAND (A=4GB, B=8GB, C=16GB, D=32GB, E=64GB, F=128GB, G=256GB)

SK HYNIX eMCP (H9TQ, H9HP, H9HQ):
  H9TQ = eMCP (eMMC + LPDDR). Buscar capacidade exata em preduo.com ou glochip.com.

MICRON eMCP (MTFC, MT29):
  MTFC = eMMC Micron. MT29 + prefixo específico pode ser eMCP.

NANYA DRAM (NT5, NT5C, NT5CC, NT6):
  NT5CC256M16 = DDR3L — 256M×16bit = 4Gbit = 512MB por die
  Regra: (número_M × bits_bus) / 8 = MB por die

QUALCOMM SoC (SM, MSM, APQ, SDM): SM8xxx=Snapdragon 8xx, SM6xxx=6xx
MEDIATEK SoC (MT6, MT8): MT6xxx=Helio/Dimensity, MT8xxx=tablet
GIGADEVICE NOR (GD25): GD25Q128=128Mbit=16MB

Responda APENAS com JSON válido (sem markdown):
{{
  "brand": "nome da marca",
  "chip_type": "tipo do chip",
  "ram": null,
  "nand": null,
  "capacity": null,
  "interface": null,
  "device": null,
  "source_url": null,
  "confidence": "high|medium|low",
  "reasoning": "de onde vieram os dados"
}}

- ram:      eMCP/uMCP APENAS — tipo + capacidade. Ex: "LPDDR4X 4GB"
- nand:     eMCP/uMCP APENAS — versão + capacidade. Ex: "eMMC 5.1 32GB"
- capacity: eMMC/UFS/DRAM standalone. Ex: "64GB", "512MB"
- chip_type: eMCP | uMCP | eMMC | UFS | LPDDR | LPDDR2 | LPDDR3 | LPDDR4 | LPDDR4X | LPDDR5 |
             DDR | DDR2 | DDR3 | DDR4 | DDR5 | SDRAM | NOR Flash | SRAM | SoC | CPU | Baseband
"""

GEMINI_EMCP_FOLLOWUP = """O chip com Part Number {pn} foi identificado como {chip_type} da marca {brand}.

Preciso ESPECIFICAMENTE das capacidades:
1. Quanto de RAM? (tipo LPDDR + GB)
2. Quanto de NAND? (versão eMMC + GB)

Busque em: preduo.com, censtry.com, serviceemmc.com, wolfchip.com, glochip.com, jotrin.com

Responda APENAS com JSON válido:
{{
  "ram": "tipo e capacidade da RAM",
  "nand": "versão eMMC e capacidade",
  "device": "dispositivo que usa este chip (se souber)",
  "source_url": "URL de onde veio a informação (se houver)",
  "confidence": "high|medium|low",
  "reasoning": "de onde vieram os dados"
}}
"""

GEMINI_MODELS_FALLBACK = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]


def _get_api_key() -> str:
    from django.conf import settings
    return getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")


def _extract_json_from_text(raw: str) -> dict | None:
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    break
    return None


def _gemini_api_call(url: str, prompt: str, use_grounding: bool, timeout: int = 20) -> str | None:
    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
    }
    if use_grounding:
        payload["tools"] = [{"google_search": {}}]
    else:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        parts = []
        for cand in data.get("candidates", []):
            for p in cand.get("content", {}).get("parts", []):
                if "text" in p:
                    parts.append(p["text"])
        return "".join(parts).strip() or None
    except urllib.error.HTTPError as e:
        if e.code in (400, 403):
            raise
        return None
    except Exception:
        return None


def _gemini_lookup(pn: str, family_hint: str = "") -> dict | None:
    """Consulta Gemini com Google Search grounding. Fallback sem grounding se necessário."""
    api_key = _get_api_key()
    if not api_key:
        return None

    hint_text = f"Contexto já identificado: {family_hint}\n" if family_hint else ""
    prompt = GEMINI_PROMPT.format(pn=pn, family_hint=hint_text)

    for model in GEMINI_MODELS_FALLBACK:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        # Tentativa 1: com grounding
        try:
            raw = _gemini_api_call(url, prompt, use_grounding=True)
            if raw:
                result = _extract_json_from_text(raw)
                if result and result.get("chip_type"):
                    result["_grounded"] = True
                    return result
        except urllib.error.HTTPError as e:
            if e.code not in (400, 403):
                continue

        # Tentativa 2: sem grounding
        try:
            raw = _gemini_api_call(url, prompt, use_grounding=False)
            if raw:
                result = _extract_json_from_text(raw)
                if result and result.get("chip_type"):
                    result["_grounded"] = False
                    return result
        except Exception:
            pass

    return None


def _gemini_emcp_followup(pn: str, chip_type: str, brand: str) -> dict | None:
    """Segundo chamado cirúrgico para eMCP sem capacidade RAM/NAND."""
    api_key = _get_api_key()
    if not api_key:
        return None

    prompt = GEMINI_EMCP_FOLLOWUP.format(pn=pn, chip_type=chip_type, brand=brand or "desconhecida")

    for model in GEMINI_MODELS_FALLBACK:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        for use_grounding in (True, False):
            try:
                raw = _gemini_api_call(url, prompt, use_grounding=use_grounding, timeout=20)
                if raw:
                    result = _extract_json_from_text(raw)
                    if result and (
                        _CAP_RE.search(str(result.get("ram") or "")) or
                        _CAP_RE.search(str(result.get("nand") or ""))
                    ):
                        return result
            except urllib.error.HTTPError as e:
                if e.code in (400, 403):
                    break
            except Exception:
                pass

    return None


def _specs_are_complete(specs: dict) -> bool:
    """Gate de qualidade antes de persistir no banco."""
    chip_type = (specs.get("chip_type") or "").lower().replace(" ", "")
    if not chip_type:
        return False
    if chip_type in ("soc", "cpu", "baseband"):
        return bool(specs.get("brand"))
    if chip_type in ("emcp", "umcp"):
        return bool(
            _CAP_RE.search(str(specs.get("ram") or "")) and
            _CAP_RE.search(str(specs.get("nand") or ""))
        )
    if chip_type in ("norflash", "sram"):
        return bool(
            _CAP_RE.search(str(specs.get("capacity") or "")) or
            specs.get("interface")
        )
    return bool(_CAP_RE.search(str(specs.get("capacity") or "")))


def _save_gemini_to_db(pn: str, specs: dict):
    """Salva resultado do Gemini no banco com status='enriched'."""
    try:
        brand_name = specs.get("brand", "Desconhecido")
        conf_raw   = specs.get("confidence", "low")
        conf_map   = {"high": "ai_high", "medium": "ai_medium", "low": "ai_low"}
        confidence = conf_map.get(conf_raw, "ai_low")

        brand, _ = Brand.objects.get_or_create(
            name__iexact=brand_name,
            defaults={
                "name": brand_name,
                "code": brand_name.upper()[:10].replace(" ", ""),
            }
        )
        source, _ = Source.objects.get_or_create(
            url=f"gemini:{pn}",
            defaults={"name": "Gemini Live Search", "src_type": "ai"}
        )
        family = _match_family(pn)

        part, created = KnownPart.objects.get_or_create(
            part_number=pn,
            defaults={
                "brand":      brand,
                "family":     family,
                "status":     "enriched",
                "chip_type":  specs.get("chip_type") or "",
                "emcp_ram":   specs.get("ram")       or "",
                "emcp_nand":  specs.get("nand")      or "",
                "capacity":   specs.get("capacity")  or "",
                "interface":  specs.get("interface") or "",
                "device":     specs.get("device")    or "",
                "notes":      str(specs.get("reasoning") or ""),
                "confidence": confidence,
                "source":     source,
                "source_url": f"gemini:{pn}",
            }
        )
        if not created:
            changed = False
            updates = {
                "chip_type": specs.get("chip_type"),
                "capacity":  specs.get("capacity"),
                "interface": specs.get("interface"),
                "device":    specs.get("device"),
                "emcp_ram":  specs.get("ram"),
                "emcp_nand": specs.get("nand"),
            }
            for field, val in updates.items():
                if val and not getattr(part, field):
                    setattr(part, field, val)
                    changed = True
            if part.status == "raw":
                part.status = "enriched"
                changed = True
            if changed:
                part.save()
        return part
    except Exception:
        return None


def _build_result_from_gemini(pn: str, specs: dict, part) -> dict:
    chip_type = specs.get("chip_type", "")
    is_emcp   = chip_type in ("eMCP", "uMCP")
    family    = _match_family(pn)
    conf_map  = {"high": "ai_high", "medium": "ai_medium", "low": "ai_low"}

    return {
        "pn":            pn,
        "known":         True,
        "known_exact":   part is not None,
        "chip_type":     chip_type,
        "subtype":       specs.get("subtype", ""),
        "interface":     specs.get("interface", ""),
        "family_prefix": family.prefix if family else "",
        "brand":         specs.get("brand", ""),
        "is_emcp":       is_emcp,
        "tip":           specs.get("reasoning", ""),
        "reasoning":     [],
        "doc_url":       _doc_url(family),
        "capacity":      specs.get("capacity"),
        "dram_density":  None,
        "emcp_ram":      specs.get("ram"),
        "emcp_nand":     specs.get("nand"),
        "emcp_device":   specs.get("device") if is_emcp else None,
        "emcp_source":   conf_map.get(specs.get("confidence", "low"), "ai_low"),
        "device":        specs.get("device") if not is_emcp else None,
        "confidence":    conf_map.get(specs.get("confidence", "low"), "ai_low"),
        "source_url":    specs.get("source_url"),
        "from_web":      True,
        "gemini_found":  True,
        "suffix_note":   None,
        "remarked_flag": False,
        "fuzzy_suggestions": [],
    }


# ── Helpers de logging ─────────────────────────────────────────────────────────

def _log_search(pn: str, found: bool, source_used: str = ""):
    try:
        SearchLog.objects.create(part_number=pn, found=found, source_used=source_used)
    except Exception:
        pass


def _log_unknown(pn: str):
    try:
        UnknownChip.objects.get_or_create(part_number=pn)
    except Exception:
        pass


# ── Ponto de entrada público ───────────────────────────────────────────────────

def classify(pn_raw: str) -> dict:
    """
    Classifica um Part Number.

    Fluxo:
      1. Banco exato (enriched) → resultado completo
      2. Gramática da família   → decodificação + Gemini se campos essenciais vazios
      3. Gemini puro            → PN desconhecido
      4. Fuzzy matching         → sugestões de digitação
    """
    pn = pn_raw.upper().strip()
    pn = re.sub(r"[^A-Z0-9]", "", pn)

    if not pn:
        return {"pn": pn_raw, "known": False, "error": "PN inválido"}

    # ── 1. Busca exata no banco ──────────────────────────────────────────────
    try:
        known = KnownPart.objects.select_related("family", "brand", "family__doc_page").get(
            part_number=pn, status="enriched"
        )
        fam = known.family or _match_family(pn)
        if fam:
            result = _result_from_known(pn, known, fam)
        else:
            result = {
                "pn":           pn,
                "known":        True,
                "known_exact":  True,
                "chip_type":    known.chip_type,
                "subtype":      known.subtype,
                "brand":        known.brand.name,
                "capacity":     known.capacity,
                "emcp_ram":     known.emcp_ram,
                "emcp_nand":    known.emcp_nand,
                "device":       known.device,
                "confidence":   known.confidence,
                "source_url":   known.source_url,
                "is_emcp":      bool(known.emcp_ram),
                "tip":          known.notes or "",
                "reasoning":    [],
                "from_web":     False,
                "doc_url":      None,
                "remarked_flag": False,
                "fuzzy_suggestions": [],
                "interface":    known.interface,
                "family_prefix": "",
            }
        _log_search(pn, found=True, source_used="db_exact")
        return result
    except KnownPart.DoesNotExist:
        pass

    # ── 2. Gramática da família ──────────────────────────────────────────────
    fam = _match_family(pn)
    if fam:
        grammar_result = _result_from_family(pn, fam)

        # Verifica se PN existe como raw (coletado mas não enriquecido)
        is_raw_in_db = KnownPart.objects.filter(part_number=pn, status="raw").exists()
        grammar_result["raw_in_db"] = is_raw_in_db

        # Decide se precisa do Gemini para completar
        missing_emcp = grammar_result.get("is_emcp") and not (
            _CAP_RE.search(str(grammar_result.get("emcp_ram", ""))) and
            _CAP_RE.search(str(grammar_result.get("emcp_nand", "")))
        )
        missing_cap = not grammar_result.get("is_emcp") and not _CAP_RE.search(
            str(grammar_result.get("capacity", "") or grammar_result.get("dram_density", "") or "")
        )

        if missing_emcp or missing_cap:
            hint = f"{fam.chip_type} {fam.subtype or ''} da família '{fam.prefix}'"
            specs = _gemini_lookup(pn, family_hint=hint)

            if specs is not None:
                if not specs.get("chip_type"):
                    specs["chip_type"] = fam.chip_type

                # Segundo chamado cirúrgico para eMCP sem capacidade
                chip_t = (specs.get("chip_type") or "").lower()
                if chip_t in ("emcp", "umcp"):
                    has_ram  = _CAP_RE.search(str(specs.get("ram") or ""))
                    has_nand = _CAP_RE.search(str(specs.get("nand") or ""))
                    if not has_ram or not has_nand:
                        followup = _gemini_emcp_followup(
                            pn, specs.get("chip_type", "eMCP"), specs.get("brand", "")
                        )
                        if followup:
                            for key in ("ram", "nand", "device", "source_url"):
                                if followup.get(key) and not specs.get(key):
                                    specs[key] = followup[key]

                if _specs_are_complete(specs):
                    _save_gemini_to_db(pn, specs)

                # Mescla dados Gemini
                if specs.get("capacity"):
                    grammar_result["capacity"] = specs["capacity"]
                if grammar_result.get("is_emcp"):
                    if specs.get("ram"):
                        grammar_result["emcp_ram"]  = specs["ram"]
                    if specs.get("nand"):
                        grammar_result["emcp_nand"] = specs["nand"]
                    if specs.get("device"):
                        grammar_result["emcp_device"] = specs["device"]
                    grammar_result["emcp_source"] = "gemini"
                else:
                    if specs.get("device"):
                        grammar_result["device"] = specs["device"]
                    if specs.get("interface") and not grammar_result.get("interface"):
                        grammar_result["interface"] = specs["interface"]

                grammar_result["gemini_found"]  = True
                grammar_result["known_exact"]   = True
            else:
                grammar_result["gemini_searched"] = True
                grammar_result["gemini_found"]    = False

        # Double-check: compara gramática com banco se PN existir enriquecido
        # (pode ter sido salvo pelo Gemini acima — rever)
        try:
            db_part = KnownPart.objects.get(part_number=pn, status="enriched")
            if db_part.family:
                db_result = _result_from_known(pn, db_part, db_part.family)
                if _check_remarked(grammar_result, db_result):
                    grammar_result["remarked_flag"] = True
                    grammar_result["remarked_note"] = (
                        f"⚠️ Atenção: gramática indica {grammar_result.get('capacity') or grammar_result.get('dram_density')}, "
                        f"banco confirma {db_result.get('capacity') or db_result.get('dram_density')}. "
                        f"Verificar possível chip remarked."
                    )
        except KnownPart.DoesNotExist:
            pass

        _log_search(pn, found=True, source_used="grammar")
        return grammar_result

    # ── 3. Gemini puro (prefixo desconhecido) ────────────────────────────────
    _log_unknown(pn)
    specs = _gemini_lookup(pn)

    if specs and specs.get("chip_type"):
        chip_t = (specs.get("chip_type") or "").lower()
        if chip_t in ("emcp", "umcp"):
            has_ram  = _CAP_RE.search(str(specs.get("ram") or ""))
            has_nand = _CAP_RE.search(str(specs.get("nand") or ""))
            if not has_ram or not has_nand:
                followup = _gemini_emcp_followup(
                    pn, specs.get("chip_type", "eMCP"), specs.get("brand", "")
                )
                if followup:
                    for key in ("ram", "nand", "device", "source_url"):
                        if followup.get(key) and not specs.get(key):
                            specs[key] = followup[key]

        part = _save_gemini_to_db(pn, specs) if _specs_are_complete(specs) else None
        result = _build_result_from_gemini(pn, specs, part)
        _log_search(pn, found=True, source_used="gemini")
        return result

    # ── 4. Fuzzy matching como sugestão ──────────────────────────────────────
    suggestions = _fuzzy_candidates(pn)
    _log_search(pn, found=False, source_used="not_found")

    return {
        "pn":               pn,
        "known":            False,
        "from_web":         True,
        "gemini_found":     False,
        "gemini_searched":  True,
        "fuzzy_suggestions": [s.part_number for s in suggestions],
    }
