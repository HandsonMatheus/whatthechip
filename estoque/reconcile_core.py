"""
estoque/reconcile_core.py
=========================
Lógica PURA (sem Django) de reconciliação de estoque por categoria do lote #039.

Contexto: o operador adicionou chips ao estoque FÍSICO e esqueceu de lançá-los
no sistema. O físico foi recontado caixa a caixa (planilha do operador) e
consolidado em RECOUNT_039 (categoria -> total físico). Para cada categoria
calculamos a diferença (físico − sistema) que falta lançar.

⚠ IMPORTANTE — sem PN inventado:
O modelo exato dos chips esquecidos foi perdido. NÃO criamos entradas novas com
part numbers fictícios. Em vez disso, o management command soma a diferença na
QUANTIDADE de um chip REAL que já existe naquela categoria no lote (o de maior
quantidade = o "mais comum" já lançado pelo operador). Nenhum PN falso entra no
sistema. Este módulo só faz a matemática por categoria; quem escolhe o chip real
e grava é o command.

Livre de Django de propósito, para ser testado isolado (ver test_reconcile_039.py).
"""

import re

# Marca usada APENAS pela tentativa antiga (que criava entradas filler). O
# command novo procura e remove qualquer resíduo com esta marca antes de operar.
RECOUNT_SOURCE = "recount_039"

LOTE = 39  # lote alvo (#039)


def _extract_gb(text: str) -> str:
    """
    Extrai o valor em GB de uma string de capacidade. Mesma semântica do
    estoque.views._extract_gb (não captura o ".1" de "eMMC 5.1").
        '8GB' -> '8'  |  '1.5GB' -> '1.5'  |  'eMMC 5.1 16GB' -> '16'
    """
    if not text:
        return ""
    m = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*GB", text, re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1)
    if val.endswith(".0"):
        val = val[:-2]
    return val


def category_key(chip_type="", capacity="", emcp_nand="", emcp_ram="",
                 is_emcp=False, interface=""):
    """
    Reduz uma entrada de estoque à MESMA granularidade da planilha do operador.
    Retorna a chave canônica (ex.: "EMCP 8+1", "EMMC 16GB", "D4 4GB",
    "UFS 64GB") ou None quando a entrada não cai em nenhuma categoria do recount.

    - eMCP: agrupa por NAND+RAM (ex.: "EMCP 8+1"). uMCP vira "UMCP ..." e fica
      fora do recount (nunca é fundido com eMCP).
    - RAM avulsa: normaliza LPDDR3/LPDDR4/LPDDR4X -> "D3"/"D4". LPDDR4X conta D4.
    """
    ct = (chip_type or "").lower()
    iface = (interface or "").lower()

    is_umcp = "umcp" in ct
    is_emcp_like = (is_emcp or "emcp" in ct) and not is_umcp

    if is_emcp_like:
        nand = _extract_gb(emcp_nand)
        ram = _extract_gb(emcp_ram)
        return f"EMCP {nand}+{ram}" if (nand and ram) else None

    if is_umcp:
        nand = _extract_gb(emcp_nand)
        ram = _extract_gb(emcp_ram)
        return f"UMCP {nand}+{ram}" if (nand and ram) else "UMCP ?"

    if "ufs" in ct:
        cap = _extract_gb(capacity)
        return f"UFS {cap}GB" if cap else None

    if "emmc" in ct:
        cap = _extract_gb(capacity)
        return f"EMMC {cap}GB" if cap else None

    # RAM avulsa (móvel ou PC) — granularidade D3/D4 do operador
    cap = _extract_gb(capacity)
    blob = f"{ct} {iface}"
    if cap and ("lpddr4" in blob or "ddr4" in blob):   # cobre LPDDR4 e LPDDR4X
        return f"D4 {cap}GB"
    if cap and ("lpddr3" in blob or "ddr3" in blob):
        return f"D3 {cap}GB"
    return None


# ─── Recontagem física do lote 039 (categoria -> total físico) ────────────────
# Ordem preservada só para o relatório sair organizado.
RECOUNT_039 = [
    ("EMCP 8+1",    243),
    ("EMCP 8+2",    12),
    ("EMCP 16+1",   21),
    ("EMCP 16+1.5", 28),
    ("EMCP 16+2",   96),
    ("EMCP 32+2",   36),
    ("EMCP 32+3",   25),
    ("EMCP 64+4",   26),
    ("EMMC 8GB",    31),
    ("EMMC 16GB",   57),
    ("EMMC 32GB",   24),
    ("EMMC 64GB",   3),
    ("D3 2GB",      30),
    ("D3 3GB",      16),
    ("D4 2GB",      19),
    ("D4 3GB",      3),
    ("D4 4GB",      14),
    ("D4 6GB",      6),
    ("UFS 64GB",    9),
]


def recount_total():
    return sum(qty for _, qty in RECOUNT_039)


def self_check():
    """Consistência da tabela: chaves únicas e total esperado. [] = ok."""
    problems = []
    seen = set()
    for key, qty in RECOUNT_039:
        if key in seen:
            problems.append(f"chave duplicada: {key!r}")
        seen.add(key)
        if qty < 0:
            problems.append(f"quantidade negativa em {key!r}")
    if recount_total() != 699:
        problems.append(f"total {recount_total()} != 699 esperado")
    return problems


def compute_reconciliation(existing_counts):
    """
    Compara o estado atual do sistema (existing_counts: {category_key: qty},
    contando SÓ entradas reais) com o recount físico e devolve o plano.

    Retorna dict:
      rows:   por categoria do recount: {key, target, current, delta, action}
                - delta > 0  -> 'add'  (faltam chips; somar em um chip real)
                - delta == 0 -> 'ok'
                - delta < 0  -> 'over' (sistema > físico; só avisar)
      extras: {category_key: qty} presentes no sistema mas fora do recount
              (ex.: uMCP, 128GB) — reportadas, nunca tocadas.
      totals: agregados para o resumo.
    """
    rows = []
    add_total = 0
    for key, target in RECOUNT_039:
        current = int(existing_counts.get(key, 0))
        delta = target - current
        if delta > 0:
            action = "add"
            add_total += delta
        elif delta == 0:
            action = "ok"
        else:
            action = "over"
        rows.append(dict(key=key, target=target, current=current,
                         delta=delta, action=action))

    recount_keys = {key for key, _ in RECOUNT_039}
    extras = {k: v for k, v in existing_counts.items() if k not in recount_keys}

    totals = dict(
        recount_total=recount_total(),
        current_in_recount=sum(r["current"] for r in rows),
        to_add=add_total,
        over_categories=sum(1 for r in rows if r["action"] == "over"),
        extra_total=sum(int(v) for v in extras.values()),
    )
    return dict(rows=rows, extras=extras, totals=totals)
