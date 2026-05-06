#!/usr/bin/env python3
"""
enrich_gemini.py — Enriquecedor via Gemini API
================================================
Lê os PNs coletados pelo collect_pns.py, consulta o Gemini
com Google Search Grounding e salva os resultados no banco Django.

Design:
  - Dois modelos ativos: gemini-2.5-pro (preferencial) e gemini-2.5-flash (fallback)
  - Grounding sempre ativo — replica o comportamento do Gemini Chat
  - Retry com backoff exponencial para 503 (sobrecarga temporária)
  - Falha permanente (404, 400) descarta o modelo e passa ao próximo
  - _specs_are_complete() como gate obrigatório antes de salvar no banco
  - Processamento paralelo via --workers (padrão: 1, seguro; 3-5 para velocidade)
  - Checkpoint atômico: failed_pns sempre deduplicado
  - Correção de double-logging: StreamHandler só quando stdout é um TTY

Uso:
  cd chipid_project
  export GEMINI_API_KEY=sua_chave

  python scripts/enrich_gemini.py --brand Samsung
  python scripts/enrich_gemini.py --brand Samsung --limit 50
  python scripts/enrich_gemini.py --brand Samsung --workers 3 --limit 200
  python scripts/enrich_gemini.py --brand Samsung --force
  python scripts/enrich_gemini.py --brand Samsung --retry-failed
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent          # chipdocs/
SCRIPTS_DIR = Path(__file__).resolve().parent
STATE_DIR   = SCRIPTS_DIR / "state"                           # _enriched.json (progresso)
PNS_DIR     = BASE_DIR.parent / "chipid_data" / "state"      # _pns.json (fonte de PNs)
LOGS_DIR    = SCRIPTS_DIR / "logs"
STATE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ── Load .env ─────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _dotenv_path = BASE_DIR / ".env"
    if _dotenv_path.exists():
        load_dotenv(_dotenv_path)
except ImportError:
    pass

# ── Gemini config ──────────────────────────────────────────────────────────────
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# Apenas modelos confirmados ativos (Abril 2026).
# gemini-1.5-pro, gemini-2.0-flash, gemini-1.5-flash e gemini-1.5-flash-8b
# estão DEPRECIADOS — retornam HTTP 404 e não devem ser tentados.
GEMINI_MODELS = [
    "gemini-2.5-pro",    # maior precisão — preferencial para chips obscuros
    "gemini-2.5-flash",  # mais rápido — fallback confiável
]

# Delay base entre chamadas sequenciais (por worker).
# Com 1 worker: 2s/PN. Com 3 workers: ~0.7s efetivo/PN.
BASE_DELAY = 2.0

# Backoff para 503 (sobrecarga temporária):
# tentativa 1 → espera 5s, tentativa 2 → 15s, tentativa 3 → 30s, depois desiste.
BACKOFF_503 = [5, 15, 30]

# Hierarquia de confiança (menor índice = mais confiável)
CONFIDENCE_RANK = {
    "confirmed":   0,
    "manual":      1,
    "distributor": 2,
    "ai_high":     3,
    "ai_medium":   4,
    "ai_low":      5,
    "estimated":   6,
}

# ── Controle global de modelos mortos e quota ─────────────────────────────────
# dead_models persiste durante toda a sessão para não re-tentar modelos 404.
_dead_models: set[str]  = set()
_dead_models_lock       = threading.Lock()

# Quando a quota diária do Gemini é esgotada (RESOURCE_EXHAUSTED),
# registramos até quando não devemos tentar novamente.
_quota_exhausted_until: float = 0.0   # epoch seconds; 0 = sem restrição ativa
_quota_lock                    = threading.Lock()

# Tempo de espera padrão ao detectar quota esgotada (1 hora).
# Substituível via argumento --quota-sleep-hours na linha de comando.
QUOTA_SLEEP_SECS: int = 3600

# ── Prompts ────────────────────────────────────────────────────────────────────

_PROMPT_BASE = """Você é especialista em chips de memória e semicondutores para dispositivos eletrônicos móveis.
Pesquise o Part Number abaixo usando o Google Search.

Part Number: {pn}
Marca esperada: {brand}

⚠ REGRA CRÍTICA PARA eMCP/uMCP:
Identificar apenas que o chip É um eMCP NÃO É SUFICIENTE.
Para chips eMCP e uMCP, os campos "ram" e "nand" são OBRIGATÓRIOS com valores reais.
Se identificar como eMCP, CONTINUE pesquisando até ter: tipo LPDDR + GB de RAM e versão eMMC + GB de NAND.
Busque em: preduo.com, censtry.com, serviceemmc.com, wolfchip.com, glochip.com, jotrin.com

== GUIA DE DECODIFICAÇÃO ==

SAMSUNG eMCP (KMR, KMQ, KMD, KMF, KMK, KMG, KM3, KM5, KM8, KMV, KMN, KMI, KMJ, KME...):
  KM* = eMCP (NAND eMMC + LPDDR RAM no mesmo package)
  KLM* = eMMC standalone — posição 3: A=4GB B=8GB C=16GB D=32GB E=64GB F=128GB G=256GB
  KLU* = UFS standalone
  K4* = LPDDR/LPDDR4/DDR3/DDR4 standalone
  Exemplos: KMRH60014A=4GB eMMC+1GB LPDDR3, KMQ310013M=16GB eMMC+3GB LPDDR3

SK HYNIX eMCP (H9TQ, H9HP, H9HQ, HMCG, HMBG, HMAH):
  H9TQ/H9HP/H9HQ = eMCP (eMMC+LPDDR). HMCG/HMBG = LPDDR5 standalone.
  H26M/H26T = eMMC standalone. H28U = UFS standalone.
  LPDDR: H9HCNNN* = LPDDR4, H54G* = LPDDR5.
  Buscar capacidade exata em preduo.com ou glochip.com.

MICRON eMMC/UFS/LPDDR (MTFC, MT29F, MT29E, MTFD, MT52, MT53):
  MTFC* = eMMC (ex: MTFC8GAKAJCN = 8GB eMMC 5.1)
  MT29F*/MT29E* = NAND Flash raw
  MTFD* = SSD/UFS (ex: MTFD32G = 32GB UFS)
  MT52* = LPDDR4 (ex: MT52L256M32D4PG = 1GB LPDDR4)
  MT53* = LPDDR4X (ex: MT53D512M32D2DS = 4GB LPDDR4X)
  MT40A/MT41K = DDR4/DDR3L standalone

KIOXIA (Toshiba) eMMC/UFS (THGBM, THGBF, THGAM, THGBH, THGBI, THGBJ, TC58):
  THGBM* = eMMC 5.1 (ex: THGBMHG8C2LBAIL = 32GB)
  THGBF* = eMMC 4.5
  THG*G*/THG*F* = geração indica versão eMMC
  THGJF*/THGJB*/THGJD* = UFS 3.1
  Capacidade codificada em posições do PN — buscar datasheet.

ELPIDA LPDDR/DDR3 (EBJ, EBK, EBL, EBU, EDF, EDJ):
  EBJ* = LPDDR2 (ex: EBJ21UE8BDS0 = 2GB LPDDR2)
  EDF* = DDR3 (ex: EDF8132A3PM = 1GB DDR3)
  Estrutura: tipo + capacidade codificada em posições 3-5 do PN.

NANYA DRAM (NT5CC, NT5CB, NT5CA, NT6CL, NT8GA):
  NT5C*/NT6C* = DDR3/DDR3L (ex: NT5CC256M16ER-EK = 4Gb DDR3L)
  NT8G* = LPDDR4
  Regra: (número_M × bits_bus) / 8 = MB por die

KINGSTON módulos DDR (KVR, KHX, KSM, KCP):
  KVR{{vel}}{{tipo}}/{{cap}} — vel: 16=DDR3-1600, 26=DDR4-2666, 32=DDR4-3200, 48=DDR5-4800
  tipo: S=SODIMM laptop, N=UDIMM desktop, E=ECC
  Ex: KVR26S19S8/8=DDR4-2666 SODIMM 8GB | KVR32S22S8/16=DDR4-3200 SODIMM 16GB

SANDISK iNAND eMMC/UFS (SDINB, SDTN, SDIN5, SDIN7, SDIN8, SDCIT):
  SDINBDA/SDINBDD/SDINBDG/SDINBDE = iNAND 7xxx eMMC 5.1 (mais comuns em Android)
  SDTNQG/SDTNRG = iNAND 8EU eMMC 5.1 (geração nova)    SDTNPM = iNAND 8EU UFS 2.1
  SDIN8DE = iNAND Extreme eMMC 5.0    SDIN7/SDIN5 = eMMC legado
  Sufixo: -8G=8GB, -16G=16GB, -32G=32GB, -64G=64GB, -128G=128GB

QUALCOMM (SM, MSM, APQ): SM8xxx=Snap8xx, SM6xxx=Snap6xx
MEDIATEK (MT6, MT8): SoC (NÃO CONFUNDIR com Micron MT52/MT53)
GIGADEVICE NOR (GD25): GD25Q128=128Mbit=16MB

{brand_extra}
== EXEMPLOS ==
✗ ERRADO: {{"chip_type":"eMCP","ram":null,"nand":null}}  ← incompleto, rejeitado
✓ CORRETO: {{"chip_type":"eMCP","ram":"LPDDR3 1GB","nand":"eMMC 4.5 8GB"}}

== INSTRUÇÕES ==
1. Busque o PN na web (Google Search obrigatório) e nos seus dados de treinamento.
2. Para eMCP/uMCP: NÃO retorne sem ram e nand — busque até encontrar.
3. Se não encontrar PN exato, deduza pela estrutura do part number.
4. Se realmente não souber a capacidade, use confidence "low" e preencha o que conseguir.
5. O campo "brand" deve ser exatamente "{brand}" se confirmado.

Responda APENAS com JSON válido, sem markdown:
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

chip_type: eMCP | uMCP | eMMC | UFS | LPDDR | LPDDR2 | LPDDR3 | LPDDR4 | LPDDR4X | LPDDR5 |
           DDR | DDR2 | DDR3 | DDR4 | DDR5 | SDRAM | NOR Flash | SRAM | SoC | CPU
ram:      eMCP/uMCP APENAS. Ex: "LPDDR4X 3GB", "LPDDR3 1GB"
nand:     eMCP/uMCP APENAS. Ex: "eMMC 5.1 32GB", "eMMC 4.5 8GB"
capacity: eMMC/UFS/DRAM standalone. Ex: "64GB", "512MB"
confidence: "high" (confirmado), "medium" (deduzido por série), "low" (estimado)
"""

# Dicas extras por marca — injetadas no {brand_extra} do prompt
_BRAND_EXTRA_HINTS: dict[str, str] = {
    "Samsung": (
        "DICA SAMSUNG: Chips K4* são LPDDR/DDR standalone, não eMCP. "
        "Chips KM* são sempre eMCP. KLM* são sempre eMMC standalone.\n"
    ),
    "SK Hynix": (
        "DICA SK HYNIX: H9TQ/H9HP/H9HQ são sempre eMCP. "
        "H54G/HMCG/HMBG são LPDDR5 standalone. H26M/H26T são eMMC standalone. "
        "H28U é UFS. HCNN* é LPDDR4.\n"
    ),
    "Micron": (
        "DICA MICRON: MTFC* = eMMC (não confundir com NAND raw MT29F). "
        "MT52*/MT53* = LPDDR4/LPDDR4X standalone (não são SoC MediaTek). "
        "MTFD* = SSD/UFS. MT40A/MT41K = DDR4/DDR3.\n"
    ),
    "KIOXIA": (
        "DICA KIOXIA (antiga Toshiba): THGBM*/THGBF* = eMMC. "
        "THGJF*/THGJB*/THGJD* = UFS 3.1. TC58* = NAND raw. "
        "Marca na embalagem pode estar como 'Toshiba' em chips antigos.\n"
    ),
    "Elpida": (
        "DICA ELPIDA (adquirida pela Micron em 2013): EBJ* = LPDDR2, "
        "EDF*/EDJ* = DDR3. Chips antigos (2010-2014) para smartphones. "
        "Verificar se PN tem sufixo -DS, -AT, -BF que indica package.\n"
    ),
    "Nanya": (
        "DICA NANYA: NT5CC*/NT5CB*/NT6CL* = DDR3/DDR3L standalone. "
        "NT8G* = LPDDR4. Calcular capacidade: (número_M × bus_bits) / 8 = MB/die. "
        "Ex: NT5CC256M16 = 256M×16bit = 512MB.\n"
    ),
    "Kingston": (
        "DICA KINGSTON: Kingston faz MÓDULOS DDR (DIMMs/SODIMMs) para notebooks e desktops, "
        "NÃO fabrica dies — compra de Samsung/Micron/SK Hynix.\n"
        "chip_type deve ser DDR3, DDR4 ou DDR5 (não LPDDR).\n"
        "capacity = capacidade do módulo (4GB, 8GB, 16GB, 32GB, 64GB).\n"
        "interface = velocidade (DDR3-1600, DDR4-2666, DDR4-3200, DDR5-4800, etc.).\n"
        "Decodificação: KVR{vel}{tipo}{...}/{cap_GB}\n"
        "  vel: 13=1333MHz, 16=1600MHz (DDR3); 21=2133, 26=2666, 32=3200 (DDR4); "
        "48=4800, 52=5200, 56=5600, 64=6400 (DDR5)\n"
        "  tipo: S=SODIMM laptop, N=UDIMM desktop, E=ECC UDIMM, R=RDIMM server\n"
        "  cap: /4=4GB, /8=8GB, /16=16GB, /32=32GB, /64=64GB\n"
        "Exemplos: KVR16S11S8/4=DDR3-1600 SODIMM 4GB | KVR26S19S8/8=DDR4-2666 SODIMM 8GB\n"
        "          KVR32S22S8/8=DDR4-3200 SODIMM 8GB | KHX3200C16D4/16GX=HyperX DDR4-3200 16GB\n"
        "KHX* = HyperX gaming (DDR3/DDR4/DDR5). KSM* = Server ECC. KCP* = Compatibility.\n"
    ),
    "SanDisk": (
        "DICA SANDISK iNAND: TODOS os chips SDIN*/SDTN*/SDCIT* são eMMC ou UFS EMBUTIDOS "
        "(não são microSD nem USB). NÃO confundir com SD cards de consumo (SDSQ*).\n"
        "Decodificação da família iNAND:\n"
        "  SDINBDA* = iNAND 7550 eMMC 5.1 (16/32/64/128/256 GB)\n"
        "  SDINBDD* = iNAND 7250 eMMC 5.1 (8/16/32/64 GB) — muito comum em Android\n"
        "  SDINBDG* = iNAND 7332 eMMC 5.1 (8/16/32/64 GB) — muito comum em Android\n"
        "  SDINBDE* = iNAND 7132 eMMC 5.1 (4/8/16 GB)\n"
        "  SDIN8DE* = iNAND Extreme eMMC 5.0 HS400 (8/16/32/64 GB)\n"
        "  SDIN7DU*/SDIN7DP* = iNAND Ultra eMMC 4.41 (8/16/32 GB)\n"
        "  SDIN5C* = iNAND eMMC 4.3/4.5 legado (4/8/16/32 GB)\n"
        "  SDTNQG*/SDTNRG* = iNAND 8EU eMMC 5.1 HS400 (8/16/32/64 GB)\n"
        "  SDTNPM* = iNAND 8EU UFS 2.1\n"
        "  SDCIT* = iNAND Industrial eMMC/UFS (grade industrial)\n"
        "Sufixo de capacidade: -4G=4GB, -8G=8GB, -16G=16GB, -32G=32GB, -64G=64GB, -128G=128GB\n"
        "Sufixo de grade: sem sufixo=commercial, -I1=industrial, -XA=automotive\n"
    ),
}


def _build_prompt(pn: str, brand: str = "") -> str:
    """Monta o prompt com dicas específicas da marca."""
    brand_extra = _BRAND_EXTRA_HINTS.get(brand, "")
    return _PROMPT_BASE.format(pn=pn, brand=brand or "desconhecida", brand_extra=brand_extra)


# Mantém PROMPT_TEMPLATE para retrocompatibilidade (uso externo/testes)
PROMPT_TEMPLATE = _PROMPT_BASE

EMCP_FOLLOWUP_TEMPLATE = """O chip {pn} foi identificado como {chip_type} da marca {brand}.

Preciso ESPECIFICAMENTE das capacidades de memória:
1. Quanto de RAM? (tipo LPDDR + GB exato)
2. Quanto de NAND? (versão eMMC + GB exato)

Busque "{pn}" em: preduo.com, censtry.com, serviceemmc.com, wolfchip.com, glochip.com, jotrin.com

Responda APENAS com JSON válido:
{{
  "ram": "tipo e capacidade da RAM",
  "nand": "versão eMMC e capacidade",
  "device": "dispositivo (se souber)",
  "source_url": "URL de onde veio (se houver)",
  "confidence": "high|medium|low",
  "reasoning": "de onde vieram os dados"
}}
"""

_CAP_RE = re.compile(r"\d+\s*[GMK]B", re.I)


# ── Claude API fallback ───────────────────────────────────────────────────────

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Prompt Claude — mesmo objetivo que o Gemini, sem grounding nativo
# mas com web_search tool do Anthropic (se disponível no plano)
CLAUDE_PROMPT_TEMPLATE = """You are an expert in electronic memory chips and semiconductors.
Find specifications for the following Part Number.

Part Number: {pn}

Search for this PN on the web. Look in: preduo.com, censtry.com, serviceemmc.com,
wolfchip.com, glochip.com, jotrin.com, alldatasheet.com and manufacturer datasheets.

CRITICAL RULE FOR eMCP/uMCP chips:
If you identify it as eMCP or uMCP, you MUST find both:
- RAM: LPDDR type and capacity in GB (e.g., "LPDDR4X 3GB")
- NAND: eMMC version and capacity in GB (e.g., "eMMC 5.1 32GB")

Samsung eMCP quick guide:
- KM* prefix = eMCP (NAND + LPDDR in one package)
- KLM* prefix = eMMC standalone (position 3: A=4GB B=8GB C=16GB D=32GB E=64GB F=128GB G=256GB)
- KLU* prefix = UFS standalone

Respond ONLY with valid JSON, no markdown:
{{
  "brand": "brand name",
  "chip_type": "eMCP|uMCP|eMMC|UFS|LPDDR|LPDDR4|LPDDR5|DDR3|DDR4|NOR Flash|SRAM|SoC",
  "ram": null,
  "nand": null,
  "capacity": null,
  "interface": null,
  "device": null,
  "source_url": null,
  "confidence": "high|medium|low",
  "reasoning": "where the data came from"
}}"""


def claude_fallback(pn: str, logger: logging.Logger) -> dict | None:
    """
    Usa a API do Claude (Anthropic) como fallback quando o Gemini falhou ou
    retornou specs incompletas.

    Requer ANTHROPIC_API_KEY no .env. Se não configurada, retorna None silenciosamente.

    Por que Claude como fallback e não como verificação paralela:
    - Dados de treino diferentes → cobertura complementar ao Gemini
    - Custo controlado: só ativa quando Gemini falhou (não em todo PN)
    - Claude com web_search tool (Anthropic beta) se disponível no plano,
      caso contrário usa só conhecimento de treino
    """
    if not ANTHROPIC_KEY:
        return None  # não configurado — ignora silenciosamente

    prompt = CLAUDE_PROMPT_TEMPLATE.format(pn=pn)

    try:
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        }

        # Adiciona web_search tool se disponível (Anthropic beta)
        # O tool só ativa se o plano suportar — caso contrário é ignorado
        payload["tools"] = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,
            }
        ]

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type":         "application/json",
                "x-api-key":            ANTHROPIC_KEY,
                "anthropic-version":    "2023-06-01",
                "anthropic-beta":       "web-search-2025-03-05",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())

        # Extrai texto das partes de conteúdo (ignora tool_use blocks)
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        raw = "\n".join(text_parts).strip()
        if not raw:
            return None

        result = _extract_json(raw)
        if result and result.get("chip_type"):
            conf = result.get("confidence", "low")
            logger.info(f"  ✓ Claude fallback: {result.get('chip_type')} | conf={conf}")
            return result

    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Plano não suporta web_search — tenta sem o tool
            try:
                payload_no_tool = {k: v for k, v in payload.items() if k != "tools"}
                req2 = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=json.dumps(payload_no_tool).encode(),
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         ANTHROPIC_KEY,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req2, timeout=45) as resp:
                    data = json.loads(resp.read())
                text_parts = [
                    b.get("text", "") for b in data.get("content", [])
                    if b.get("type") == "text"
                ]
                raw = "\n".join(text_parts).strip()
                result = _extract_json(raw)
                if result and result.get("chip_type"):
                    logger.info(f"  ✓ Claude fallback (sem web search): {result.get('chip_type')}")
                    return result
            except Exception:
                pass
        elif e.code != 401:
            logger.warning(f"  Claude fallback HTTP {e.code}")
    except Exception as e:
        logger.warning(f"  Claude fallback erro: {e}")

    return None


# ── Decode local (ChipFamily) ──────────────────────────────────────────────────

def try_local_decode(pn: str, brand_name: str) -> dict | None:
    """
    Tenta decodificar um PN localmente usando os mapas de ChipFamily do banco.

    GARANTIAS DE SEGURANÇA:
    - Só opera em famílias que JÁ estão no banco com decode_cap_map configurado
    - Famílias novas/desconhecidas retornam None → caem no Gemini normalmente
    - O resultado é marcado com confidence="distributor" (mais alta que ai_high)
      pois vem de padrões documentados, não de inferência
    - Nunca bloqueia o fluxo — qualquer falha retorna None silenciosamente

    Quando é útil:
    - Samsung KLM*: posição 3 do PN indica capacidade NAND (A=4GB...G=256GB)
    - Samsung KLU*: posição 3 indica capacidade UFS
    - Qualquer família com decode_cap_pos + decode_cap_map cadastrados no banco

    Retorna dict no mesmo formato que gemini_search(), ou None se não conseguiu
    decodificar com certeza.
    """
    try:
        # Setup Django se necessário (chamado antes de setup_django() na main)
        if not _django_ready:
            return None

        from chips.models import ChipFamily, DecodeMap

        # Encontra a família pelo prefixo mais longo que bata
        best_family = None
        best_len    = 0
        for fam in ChipFamily.objects.filter(active=True, decode_cap_pos__isnull=False):
            if pn.startswith(fam.prefix) and len(fam.prefix) > best_len:
                best_family = fam
                best_len    = len(fam.prefix)

        if not best_family:
            return None  # família não tem decode configurado → vai para Gemini

        fam = best_family

        # eMCP: decode local não é confiável o suficiente (ram + nand dependem do mercado)
        # → só decodifica eMMC/UFS standalone e DRAM standalone
        if fam.is_emcp:
            return None

        result = {
            "brand":      brand_name,
            "chip_type":  fam.chip_type,
            "capacity":   None,
            "interface":  fam.interface or None,
            "ram":        None,
            "nand":       None,
            "device":     None,
            "source_url": f"local_decode:{fam.prefix}",
            "confidence": "medium",  # decodificado por padrão, não confirmado por fonte
            "reasoning":  f"Decodificado localmente pela família {fam.prefix} (decode_cap_pos={fam.decode_cap_pos})",
        }

        # Capacidade pelo mapa de posição
        if fam.decode_cap_pos is not None and fam.decode_cap_map:
            pos = fam.decode_cap_pos
            if len(pn) > pos:
                char = pn[pos]
                entry = DecodeMap.objects.filter(
                    map_name=fam.decode_cap_map, char_key=char
                ).first()
                if entry and entry.val_primary:
                    result["capacity"] = entry.val_primary
                    result["confidence"] = "distributor"  # padrão mecânico confirmado

        # Geração / interface pelo mapa de geração
        if fam.decode_gen_pos is not None and fam.decode_gen_map:
            pos = fam.decode_gen_pos
            if len(pn) > pos:
                char = pn[pos]
                entry = DecodeMap.objects.filter(
                    map_name=fam.decode_gen_map, char_key=char
                ).first()
                if entry and entry.val_primary:
                    result["interface"] = entry.val_primary

        # Só retorna se conseguiu decodificar ao menos a capacidade
        if result["capacity"]:
            return result

    except Exception:
        pass  # qualquer erro → cai no Gemini normalmente

    return None


# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging(log_file: Path) -> logging.Logger:
    """
    Configura logging sem double-logging.
    O double-logging acontecia porque _launch_subprocess redireciona stdout
    para o arquivo de log E o StreamHandler também escrevia no stdout.
    Solução: só adiciona StreamHandler quando stdout é um TTY real (modo interativo).
    """
    logger = logging.getLogger("enrich")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # FileHandler: sempre presente
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # StreamHandler: só quando rodando interativamente (não como subprocesso com stdout redirecionado)
    if sys.stdout.isatty():
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger


# ── Gemini API ─────────────────────────────────────────────────────────────────

def _get_grounding_tool(model: str) -> dict:
    """Retorna o tool de grounding correto para a família do modelo."""
    # gemini-2.5-* e gemini-2.0-* usam google_search
    if any(x in model for x in ("2.5", "2.0")):
        return {"google_search": {}}
    # gemini-1.5-* usaria google_search_retrieval — mas esses modelos estão depreciados
    return {"google_search": {}}


def _call_gemini(url: str, prompt: str, model: str, use_grounding: bool = True,
                 timeout: int = 45) -> str | None:
    """
    Faz uma chamada à Gemini API e retorna o texto bruto.
    Com grounding: não usa responseMimeType (incompatível com google_search).
    Sem grounding: usa responseMimeType=application/json.

    Raises:
        urllib.error.HTTPError — para o caller decidir o que fazer (404 vs 429 vs 503)
    """
    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1024,
        },
    }

    if use_grounding:
        payload["tools"] = [_get_grounding_tool(model)]
    else:
        payload["generationConfig"]["responseMimeType"] = "application/json"

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


def _extract_json(raw: str) -> dict | None:
    """
    Extrai o primeiro objeto JSON de um texto livre.
    Robusto contra markdown, texto antes/depois, e JSON quebrado.
    """
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


def _call_with_backoff(url: str, prompt: str, model: str, use_grounding: bool,
                       logger: logging.Logger) -> str | None:
    """
    Chama a API com retry automático para 503 (sobrecarga temporária).
    Para 404/400/403: levanta HTTPError imediatamente (falha permanente).
    Para 429:
      - Se body contém RESOURCE_EXHAUSTED → quota diária esgotada.
        Dorme QUOTA_SLEEP_SECS (padrão 1h) e tenta novamente.
        Repete até 3 vezes (3h no total antes de desistir).
      - Caso contrário → rate limit por minuto. Dorme 60s e tenta 1x mais.
    """
    global _quota_exhausted_until

    # ── Verifica se estamos em modo quota-sleep ───────────────────────────────
    with _quota_lock:
        if _quota_exhausted_until > 0:
            remaining = _quota_exhausted_until - time.time()
            if remaining > 0:
                logger.warning(
                    f"  ⏸  Quota esgotada — aguardando mais {remaining/60:.0f}min..."
                )
                time.sleep(remaining)
            _quota_exhausted_until = 0.0

    quota_retries = 0
    for attempt, wait in enumerate(BACKOFF_503 + [None]):
        try:
            return _call_gemini(url, prompt, model, use_grounding)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass

            if e.code == 503:
                if wait is not None:
                    logger.warning(
                        f"  ⏳ 503 [{model}] sobrecarga — aguardando {wait}s "
                        f"(tentativa {attempt + 1}/{len(BACKOFF_503)})"
                    )
                    time.sleep(wait)
                    continue
                else:
                    logger.warning(f"  ✗ 503 [{model}] — esgotadas {len(BACKOFF_503)} tentativas")
                    return None

            if e.code == 429:
                is_resource_exhausted = (
                    "RESOURCE_EXHAUSTED" in body or
                    "quota" in body.lower() or
                    "rateLimitExceeded" in body
                )
                if is_resource_exhausted and quota_retries < 3:
                    quota_retries += 1
                    sleep_secs = QUOTA_SLEEP_SECS
                    wake_at    = datetime.fromtimestamp(
                        time.time() + sleep_secs
                    ).strftime("%H:%M")
                    logger.warning(
                        f"  💤 429 RESOURCE_EXHAUSTED [{model}] — quota diária esgotada. "
                        f"Dormindo {sleep_secs // 3600}h (tentativa {quota_retries}/3). "
                        f"Retomando às ~{wake_at}..."
                    )
                    with _quota_lock:
                        _quota_exhausted_until = time.time() + sleep_secs
                    time.sleep(sleep_secs)
                    with _quota_lock:
                        _quota_exhausted_until = 0.0
                    continue  # tenta o loop novamente após dormir
                else:
                    # Rate limit de curto prazo (não RESOURCE_EXHAUSTED)
                    logger.warning(f"  ⏳ 429 [{model}] rate limit — aguardando 60s")
                    time.sleep(60)
                    try:
                        return _call_gemini(url, prompt, model, use_grounding)
                    except Exception:
                        return None

            # 404, 400, 403 — falha permanente deste modelo
            raise  # propaga para o caller eliminar o modelo da lista

        except Exception as e:
            logger.warning(f"  ✗ erro inesperado [{model}]: {e}")
            return None

    return None


def gemini_search(pn: str, logger: logging.Logger, brand: str = "") -> dict | None:
    """
    Consulta o Gemini para obter specs do chip.

    Estratégia por modelo:
    1. Tenta com Google Search Grounding (melhor qualidade, busca na web em tempo real)
    2. Fallback sem grounding se grounding retornar erro 400/403
    3. Retry automático para 503 com backoff exponencial
    4. 404 → elimina o modelo permanentemente na sessão (global _dead_models)
    5. Todos os modelos falharam → retorna None

    `brand` é passado ao prompt para ajudar o Gemini a focar na marca correta.
    """
    if not GEMINI_KEY:
        logger.error("GEMINI_API_KEY não definida.")
        return None

    prompt = _build_prompt(pn, brand)

    for model in GEMINI_MODELS:
        with _dead_models_lock:
            if model in _dead_models:
                continue

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_KEY}"
        )

        # ── Tentativa com grounding ───────────────────────────────────────────
        grounded_ok = True
        try:
            raw = _call_with_backoff(url, prompt, model, use_grounding=True, logger=logger)
            if raw:
                result = _extract_json(raw)
                if result and result.get("chip_type"):
                    conf = result.get("confidence", "low")
                    logger.info(f"  ✓ {model} [grounded]: {result.get('chip_type')} | conf={conf}")
                    return _apply_emcp_followup(pn, result, logger)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.warning(f"  ✗ HTTP 404 [{model}] — modelo depreciado, descartando")
                with _dead_models_lock:
                    _dead_models.add(model)
                continue
            if e.code in (400, 403):
                # Grounding não suportado neste plano/modelo — tenta sem grounding
                grounded_ok = False
            else:
                logger.warning(f"  HTTP {e.code} [{model}] (grounded)")

        # ── Fallback sem grounding ────────────────────────────────────────────
        if not grounded_ok:
            try:
                raw = _call_with_backoff(url, prompt, model, use_grounding=False, logger=logger)
                if raw:
                    result = _extract_json(raw)
                    if result and result.get("chip_type"):
                        conf = result.get("confidence", "low")
                        logger.info(f"  ✓ {model} [sem grounding]: {result.get('chip_type')} | conf={conf}")
                        return _apply_emcp_followup(pn, result, logger)
                    logger.warning(f"  {model}: JSON sem chip_type")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    logger.warning(f"  ✗ HTTP 404 [{model}] — modelo depreciado, descartando")
                    with _dead_models_lock:
                        _dead_models.add(model)
                elif e.code == 429:
                    logger.warning(f"  ⏳ 429 [{model}] rate limit")
                else:
                    logger.warning(f"  HTTP {e.code} [{model}] (sem grounding)")
            except Exception as e:
                logger.warning(f"  Erro [{model}]: {e}")

    return None


def _gemini_emcp_followup(pn: str, chip_type: str, brand: str,
                           logger: logging.Logger) -> dict | None:
    """
    Segunda chamada cirúrgica: disparada quando a primeira identificou eMCP/uMCP
    mas não retornou ram e/ou nand com valores reais.
    """
    if not GEMINI_KEY:
        return None

    prompt = EMCP_FOLLOWUP_TEMPLATE.format(pn=pn, chip_type=chip_type, brand=brand)

    for model in GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_KEY}"
        )
        for use_grounding in (True, False):
            try:
                raw = _call_with_backoff(url, prompt, model, use_grounding, logger)
                if not raw:
                    continue
                result = _extract_json(raw)
                if not result:
                    continue
                has_ram  = _CAP_RE.search(str(result.get("ram") or ""))
                has_nand = _CAP_RE.search(str(result.get("nand") or ""))
                if has_ram or has_nand:
                    tag = "grounded" if use_grounding else "sem grounding"
                    logger.info(
                        f"  ↳ followup [{tag}]: ram={result.get('ram')} "
                        f"nand={result.get('nand')}"
                    )
                    return result
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break  # modelo morto, tenta próximo
            except Exception as e:
                logger.warning(f"  followup erro [{model}]: {e}")

    return None


def _apply_emcp_followup(pn: str, specs: dict, logger: logging.Logger) -> dict:
    """
    Se specs é eMCP/uMCP sem ram ou nand reais, dispara o followup cirúrgico
    e mescla os resultados.
    """
    chip_t = (specs.get("chip_type") or "").lower().replace(" ", "")
    if chip_t not in ("emcp", "umcp"):
        return specs

    has_ram  = _CAP_RE.search(str(specs.get("ram") or ""))
    has_nand = _CAP_RE.search(str(specs.get("nand") or ""))
    if has_ram and has_nand:
        return specs

    logger.info(
        f"  ⚡ eMCP incompleto (ram={specs.get('ram')}, nand={specs.get('nand')}) "
        f"— chamando followup..."
    )
    followup = _gemini_emcp_followup(
        pn, specs.get("chip_type", "eMCP"), specs.get("brand", ""), logger
    )
    if followup:
        if followup.get("ram") and _CAP_RE.search(str(followup["ram"])):
            specs = {**specs, "ram": followup["ram"]}
        if followup.get("nand") and _CAP_RE.search(str(followup["nand"])):
            specs = {**specs, "nand": followup["nand"]}
        if followup.get("device") and not specs.get("device"):
            specs = {**specs, "device": followup["device"]}
        if followup.get("source_url") and not specs.get("source_url"):
            specs = {**specs, "source_url": followup["source_url"]}
        if followup.get("confidence") == "high" and specs.get("confidence") != "high":
            specs = {**specs, "confidence": followup["confidence"]}
    return specs


# ── Completude das specs ───────────────────────────────────────────────────────

def _specs_are_complete(specs: dict) -> bool:
    """
    Gate de qualidade: só salva no banco se as specs têm os campos essenciais.
    Chips com chip_type mas sem capacidade não são úteis e poluem o banco.
    """
    chip_type = (specs.get("chip_type") or "").lower().replace(" ", "")
    if not chip_type:
        return False

    # SoC, CPU, Baseband — tipo + brand bastam
    if chip_type in ("soc", "cpu", "baseband"):
        return bool(specs.get("brand"))

    # eMCP / uMCP — exige ram E nand com valor de capacidade real
    if chip_type in ("emcp", "umcp"):
        return bool(
            _CAP_RE.search(str(specs.get("ram") or "")) and
            _CAP_RE.search(str(specs.get("nand") or ""))
        )

    # NOR Flash, SRAM — capacity ou interface
    if chip_type in ("norflash", "nor flash", "sram"):
        return bool(
            _CAP_RE.search(str(specs.get("capacity") or "")) or
            specs.get("interface")
        )

    # eMMC, UFS, LPDDR*, DDR*, SDRAM — exige capacity com valor real
    return bool(_CAP_RE.search(str(specs.get("capacity") or "")))


# ── Django setup ───────────────────────────────────────────────────────────────

_django_ready = False
_django_lock  = threading.Lock()


def setup_django() -> bool:
    global _django_ready
    with _django_lock:
        if _django_ready:
            return True
        project_dir = BASE_DIR
        sys.path.insert(0, str(project_dir))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
        try:
            import django
            django.setup()
            _django_ready = True
            return True
        except Exception as e:
            logging.getLogger("enrich").error(f"Django não disponível: {e}")
            return False


# ── Django save ────────────────────────────────────────────────────────────────

_save_lock = threading.Lock()


def save_to_django(pn: str, specs: dict, brand_name: str) -> str:
    """
    Salva ou atualiza um chip no banco Django.
    Thread-safe via lock.
    Retorna: 'created' | 'updated' | 'skipped'
    """
    from chips.models import KnownPart, Brand, Source, ChipFamily

    conf_raw = specs.get("confidence", "low")
    conf_map = {"high": "ai_high", "medium": "ai_medium", "low": "ai_low"}
    confidence_key = conf_map.get(conf_raw, "ai_low")

    with _save_lock:
        brand, _ = Brand.objects.get_or_create(
            name__iexact=brand_name,
            defaults={
                "name": brand_name,
                "code": brand_name.upper()[:10].replace(" ", ""),
            }
        )

        src_url = specs.get("source_url") or f"gemini:{pn}"
        source, _ = Source.objects.get_or_create(
            url=src_url,
            defaults={"name": "Gemini Bulk Enrichment", "src_type": "ai"}
        )

        # Encontra família pelo prefixo mais longo
        family = None
        for fam in ChipFamily.objects.filter(active=True).order_by("priority", "-prefix"):
            if pn.startswith(fam.prefix):
                family = fam
                break

        existing = KnownPart.objects.filter(part_number=pn).first()

        if existing:
            existing_rank = CONFIDENCE_RANK.get(existing.confidence, 99)
            new_rank = CONFIDENCE_RANK.get(confidence_key, 99)

            updated = False
            # Preenche campos vazios com novos dados
            for field, value in [
                ("chip_type",  specs.get("chip_type") or ""),
                ("emcp_ram",   specs.get("ram") or ""),
                ("emcp_nand",  specs.get("nand") or ""),
                ("capacity",   specs.get("capacity") or ""),
                ("interface",  specs.get("interface") or ""),
                ("device",     specs.get("device") or ""),
            ]:
                if value and not getattr(existing, field):
                    setattr(existing, field, value)
                    updated = True

            if not existing.source_url and src_url:
                existing.source_url = src_url
                updated = True

            # Eleva confiança se novo dado é mais confiável
            if new_rank < existing_rank:
                existing.confidence = confidence_key
                existing.source = source
                updated = True

            reasoning = specs.get("reasoning", "")
            if reasoning and not existing.notes:
                existing.notes = str(reasoning)[:500]
                updated = True

            if updated:
                existing.save()
                return "updated"
            return "skipped"

        else:
            KnownPart.objects.create(
                brand=brand,
                part_number=pn,
                family=family,
                chip_type=specs.get("chip_type") or "",
                emcp_ram=specs.get("ram") or "",
                emcp_nand=specs.get("nand") or "",
                capacity=specs.get("capacity") or "",
                interface=specs.get("interface") or "",
                device=specs.get("device") or "",
                notes=str(specs.get("reasoning") or "")[:500],
                confidence=confidence_key,
                source=source,
                source_url=src_url,
            )
            return "created"


def already_enriched_in_db(pn: str) -> bool:
    """Retorna True se o PN já está no banco com confiança >= ai_high."""
    from chips.models import KnownPart
    part = KnownPart.objects.filter(part_number=pn).first()
    if not part:
        return False
    return CONFIDENCE_RANK.get(part.confidence, 99) <= CONFIDENCE_RANK["ai_high"]


# ── Job tracking ───────────────────────────────────────────────────────────────

def update_job(job_id: int | None, **kwargs):
    if not job_id:
        return
    try:
        pass  # ScrapingJob removido
        pass  # ScrapingJob nao disponivel no WhatTheChip
    except Exception:
        pass


def log_to_job(job_id: int | None, level: str, message: str):
    if not job_id:
        return
    try:
        pass  # ScrapingJob removido
        job = None  # ScrapingJob nao disponivel no WhatTheChip
        if job:
            pass  # ScrapingLog nao disponivel no WhatTheChip
    except Exception:
        pass


# ── State management ───────────────────────────────────────────────────────────

_state_lock = threading.Lock()


def load_enrich_state(brand: str) -> dict:
    path = STATE_DIR / f"{brand}_enriched.json"
    if path.exists():
        try:
            d = json.loads(path.read_text())
            # Normaliza: garante listas sem duplicatas
            d["enriched_pns"] = list(dict.fromkeys(d.get("enriched_pns", [])))
            d["failed_pns"]   = list(dict.fromkeys(d.get("failed_pns", [])))
            return d
        except Exception:
            pass
    return {"brand": brand, "enriched_pns": [], "failed_pns": []}


def save_enrich_state(brand: str, state: dict):
    """Salva estado atomicamente, sempre com listas deduplicadas."""
    with _state_lock:
        path = STATE_DIR / f"{brand}_enriched.json"
        state["updated_at"]   = datetime.now(timezone.utc).isoformat()
        # Garante deduplicação antes de salvar
        state["enriched_pns"] = list(dict.fromkeys(state.get("enriched_pns", [])))
        state["failed_pns"]   = list(dict.fromkeys(state.get("failed_pns", [])))
        # Escrita atômica via arquivo temporário
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        tmp.replace(path)


def mark_enriched(brand: str, state: dict, pn: str):
    """Marca PN como enriquecido e remove de failed se estava lá."""
    with _state_lock:
        enriched_set = set(state["enriched_pns"])
        enriched_set.add(pn)
        state["enriched_pns"] = list(enriched_set)
        failed_set = set(state["failed_pns"])
        failed_set.discard(pn)
        state["failed_pns"] = list(failed_set)


def mark_failed(brand: str, state: dict, pn: str):
    """Marca PN como falhou (deduplicado)."""
    with _state_lock:
        failed_set = set(state["failed_pns"])
        failed_set.add(pn)
        state["failed_pns"] = list(failed_set)


# ── Worker function ────────────────────────────────────────────────────────────

def process_pn(pn: str, brand: str, state: dict, logger: logging.Logger,
               job_id: int | None, delay: float) -> str:
    """
    Processa um único PN: decode local → Gemini → Claude fallback → salva.
    Retorna: 'created' | 'updated' | 'skipped' | 'incomplete' | 'error'
    Thread-safe.

    Fluxo:
    1. Decode local (ChipFamily): zero custo, instantâneo, alta confiança
       → só disponível para famílias com decode_cap_map no banco
       → eMCP sempre pula para Gemini (decode local não resolve ram+nand)
    2. Gemini com grounding: busca na web em tempo real
    3. Claude fallback: se Gemini falhou ou retornou confiança baixa
    4. Gate _specs_are_complete: só salva specs completas
    """
    try:
        # ── Etapa 1: Decode local ─────────────────────────────────────────────
        specs = try_local_decode(pn, brand)
        if specs:
            logger.info(f"  ⚡ decode local: {specs.get('chip_type')} | {specs.get('capacity')} | conf={specs.get('confidence')}")

        # ── Etapa 2: Gemini (se decode não resolveu) ──────────────────────────
        if not specs or not _specs_are_complete(specs):
            gemini_specs = gemini_search(pn, logger, brand=brand)
            if gemini_specs:
                # Gemini encontrou — usa como specs principal
                specs = gemini_specs
            elif specs:
                # Decode local trouxe algo parcial mas Gemini falhou
                # Mantém o que o decode trouxe (melhor que nada)
                logger.info(f"  ⚠ Gemini falhou — usando decode local parcial")
            # (se nem decode nem Gemini → specs permanece None)

        # ── Etapa 3: Claude fallback (se Gemini falhou ou confiança baixa) ───
        if (not specs or not _specs_are_complete(specs)):
            claude_specs = claude_fallback(pn, logger)
            if claude_specs and _specs_are_complete(claude_specs):
                specs = claude_specs

        if not specs:
            msg = f"  → nenhum modelo retornou resposta válida para {pn}"
            logger.info(msg)
            log_to_job(job_id, "warn", msg)
            mark_failed(brand, state, pn)
            return "error"

        conf = specs.get("confidence", "low")
        chip_t = specs.get("chip_type", "?")

        # Gate de qualidade: só salva specs completas
        if not _specs_are_complete(specs):
            cap_hint = (specs.get("ram") or specs.get("capacity") or
                        specs.get("nand") or "sem capacidade")
            msg = (f"  ⚠ {pn}: specs incompletas ({chip_t}, {cap_hint}) "
                   f"— não salvo no banco")
            logger.info(msg)
            log_to_job(job_id, "warn", msg)
            mark_failed(brand, state, pn)
            return "incomplete"

        status = save_to_django(pn, specs, brand)
        icon   = {"created": "✅", "updated": "🔄", "skipped": "⏭"}.get(status, "?")
        cap    = specs.get("ram") or specs.get("capacity") or specs.get("nand") or "?"
        msg    = f"  {icon} {pn}: {chip_t} | {cap} | conf={conf}"
        logger.info(msg)
        log_to_job(job_id, "ok" if status != "skipped" else "info", msg)
        mark_enriched(brand, state, pn)
        return status

    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error(f"  ✗ {pn}: erro inesperado: {e}")
        log_to_job(job_id, "error", f"  {pn}: ERRO: {e}")
        mark_failed(brand, state, pn)
        return "error"
    finally:
        time.sleep(delay)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Gemini Bulk Enrichment — enriquece PNs via Gemini com Google Search Grounding"
    )
    parser.add_argument("--brand",        default="Samsung",
                        help="Marca a enriquecer (deve ter state/{brand}_pns.json)")
    parser.add_argument("--limit",        type=int, default=2000,
                        help="Máx de chips por rodada. Padrão: 2000. Use --no-limit para sem restrição.")
    parser.add_argument("--no-limit",     action="store_true",
                        help="Processa todos os PNs sem limite (ignora --limit)")
    parser.add_argument("--workers",      type=int, default=1,
                        help="Threads paralelas (1=sequencial, 3-5=mais rápido). Padrão: 1")
    parser.add_argument("--delay",        type=float, default=BASE_DELAY,
                        help=f"Delay entre chamadas por worker (padrão: {BASE_DELAY}s)")
    parser.add_argument("--force",        action="store_true",
                        help="Reenriquece chips já processados")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Prioriza PNs que falharam em rodadas anteriores")
    parser.add_argument("--job-id",       type=int, default=None,
                        help="ID do ScrapingJob Django para atualizar progresso em tempo real")
    parser.add_argument("--quota-sleep-hours", type=float, default=1.0,
                        help="Horas para dormir quando RESOURCE_EXHAUSTED (quota diária). Padrão: 1h")
    args = parser.parse_args()

    global QUOTA_SLEEP_SECS

    brand             = args.brand
    delay             = args.delay
    workers           = max(1, min(args.workers, 10))  # clamp 1-10
    job_id            = args.job_id
    QUOTA_SLEEP_SECS  = int(args.quota_sleep_hours * 3600)

    # ── Logging ────────────────────────────────────────────────────────────────
    log_file = LOGS_DIR / f"{brand}_enrich.log"
    logger   = setup_logging(log_file)

    # ── Validações ─────────────────────────────────────────────────────────────
    if not GEMINI_KEY:
        logger.error("❌ GEMINI_API_KEY não definida. Defina no .env ou como variável de ambiente.")
        sys.exit(1)

    if not setup_django():
        sys.exit(1)

    # ── Lê PNs coletados ───────────────────────────────────────────────────────
    # Busca em PNS_DIR (chipid_data/state/) — fonte original dos PNs coletados.
    # Fallback para STATE_DIR (scripts/state/) para compatibilidade com setups antigos.
    pns_state_path = PNS_DIR / f"{brand}_pns.json"
    if not pns_state_path.exists():
        pns_state_path = STATE_DIR / f"{brand}_pns.json"
    if not pns_state_path.exists():
        logger.error(f"❌ {brand}_pns.json não encontrado.")
        logger.error(f"   Procurado em: {PNS_DIR} e {STATE_DIR}")
        logger.error(f"   Execute primeiro: python scripts/collect_pns.py --brand {brand}")
        sys.exit(1)

    pns_state = json.loads(pns_state_path.read_text())
    all_pns   = pns_state.get("pns", [])

    logger.info("=" * 60)
    logger.info(f"enrich_gemini.py — {brand}")
    logger.info(f"Modelos: {GEMINI_MODELS}")
    limit_str = "sem limite" if args.no_limit else str(args.limit)
    logger.info(f"PNs coletados: {len(all_pns)} | Workers: {workers} | Delay: {delay}s | Limite: {limit_str}")
    logger.info("=" * 60)

    # ── Carrega estado de enriquecimento ───────────────────────────────────────
    enrich_state = load_enrich_state(brand)
    already_enriched_set = set(enrich_state["enriched_pns"])
    failed_set           = set(enrich_state["failed_pns"])

    # ── Monta lista de PNs a processar ────────────────────────────────────────
    to_process = []

    if args.retry_failed:
        # Modo retry: só os que falharam anteriormente
        logger.info(f"Modo --retry-failed: {len(failed_set)} PNs com falha anterior")
        for pn in all_pns:
            if pn in failed_set:
                to_process.append(pn)
    else:
        for pn in all_pns:
            if not args.force and pn in already_enriched_set:
                continue
            if not args.force and already_enriched_in_db(pn):
                # Atualiza checkpoint local com o que está no banco
                already_enriched_set.add(pn)
                enrich_state["enriched_pns"] = list(already_enriched_set)
                continue
            to_process.append(pn)

    # Aplica limite (--no-limit desativa qualquer restrição)
    if not args.no_limit:
        to_process = to_process[:args.limit]

    retry_count = len([p for p in to_process if p in failed_set])
    logger.info(f"PNs a processar nesta rodada: {len(to_process)} (limite: {args.limit})")
    if retry_count:
        logger.info(f"  ↺ {retry_count} são retentativas de falhas anteriores")

    if not to_process:
        logger.info("✅ Nada a fazer — todos os PNs já estão enriquecidos.")
        update_job(job_id, status="done", finished_at=datetime.now(timezone.utc))
        return

    update_job(job_id, status="running", pns_found=len(all_pns),
               started_at=datetime.now(timezone.utc))
    log_to_job(job_id, "info", f"Iniciando: {len(to_process)} PNs | workers={workers}")

    # ── Processamento ──────────────────────────────────────────────────────────
    stats     = {"created": 0, "updated": 0, "skipped": 0, "incomplete": 0, "error": 0}
    processed = 0

    try:
        if workers == 1:
            # Sequencial — mais simples, sem race conditions
            for i, pn in enumerate(to_process, 1):
                logger.info(f"[{i}/{len(to_process)}] {pn}")
                log_to_job(job_id, "info", f"[{i}/{len(to_process)}] Pesquisando {pn}...")

                result = process_pn(pn, brand, enrich_state, logger, job_id, delay)
                stats[result] = stats.get(result, 0) + 1
                processed += 1

                if processed % 10 == 0:
                    save_enrich_state(brand, enrich_state)
                    update_job(job_id,
                               pns_done=stats["created"] + stats["updated"],
                               pns_skipped=stats["skipped"],
                               pns_errors=stats["error"] + stats["incomplete"])

        else:
            # Paralelo — ThreadPoolExecutor com delay por worker
            logger.info(f"  Modo paralelo: {workers} workers")
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(process_pn, pn, brand, enrich_state, logger, job_id, delay): pn
                    for pn in to_process
                }
                completed = 0
                for future in as_completed(futures):
                    pn     = futures[future]
                    completed += 1
                    result = "error"  # default — sobreescrito se future.result() ok
                    try:
                        result = future.result()
                        stats[result] = stats.get(result, 0) + 1
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        logger.error(f"  ✗ worker error [{pn}]: {e}")
                        stats["error"] = stats.get("error", 0) + 1

                    logger.info(f"[{completed}/{len(to_process)}] {pn} — {result}")
                    processed += 1

                    if completed % 10 == 0:
                        save_enrich_state(brand, enrich_state)
                        update_job(job_id,
                                   pns_done=stats["created"] + stats["updated"],
                                   pns_skipped=stats["skipped"],
                                   pns_errors=stats["error"] + stats["incomplete"])

    except KeyboardInterrupt:
        logger.warning("\nInterrompido — salvando estado...")
        save_enrich_state(brand, enrich_state)
        update_job(job_id, status="error", finished_at=datetime.now(timezone.utc))
        sys.exit(0)

    # ── Salva estado final ─────────────────────────────────────────────────────
    save_enrich_state(brand, enrich_state)

    from chips.models import KnownPart
    total_db = KnownPart.objects.count()

    total_enriched = len(enrich_state["enriched_pns"])
    total_failed   = len(enrich_state["failed_pns"])
    remaining      = max(0, len(all_pns) - total_enriched)

    summary = (
        f"\n{'=' * 60}\n"
        f"✅ Enriquecimento finalizado — {brand}\n"
        f"   Criados      : {stats.get('created', 0)}\n"
        f"   Atualizados  : {stats.get('updated', 0)}\n"
        f"   Pulados      : {stats.get('skipped', 0)}\n"
        f"   Incompletos  : {stats.get('incomplete', 0)} (specs insuficientes — serão retentados)\n"
        f"   Erros API    : {stats.get('error', 0)} (sem resposta — serão retentados)\n"
        f"   Progresso    : {total_enriched}/{len(all_pns)} enriquecidos"
        f" ({remaining} restantes, {total_failed} falhas únicas)\n"
        f"   Total no banco: {total_db} PNs\n"
        f"   {'✅ Todos enriquecidos!' if remaining == 0 else f'▶ Próxima rodada: python scripts/enrich_gemini.py --brand {brand} --limit {min(args.limit, remaining)}'}\n"
        f"   Log: {log_file}\n"
    )
    logger.info(summary)
    log_to_job(job_id, "ok", summary)
    update_job(
        job_id, status="done",
        pns_done=stats.get("created", 0) + stats.get("updated", 0),
        pns_skipped=stats.get("skipped", 0),
        pns_errors=stats.get("error", 0) + stats.get("incomplete", 0),
        finished_at=datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    main()
