"""
test_reconcile_039.py
=====================
Testes da lógica PURA de reconciliação do lote #039 (estoque/reconcile_core.py).
Não precisa de Django nem de banco:

    python3 test_reconcile_039.py

Cobre: consistência da tabela, category_key (LPDDR4X->D4, eMCP, 1.5GB, uMCP fora
do recount, sem-capacidade), compute_reconciliation (vazio, parcial, over, extras,
idempotência) e a regra "chip dominante" (maior quantidade) usada pelo command.
"""
import importlib.util
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "reconcile_core", os.path.join(_here, "estoque", "reconcile_core.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

fails = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        fails.append(name)


class FakeEntry:
    """Imita InventoryEntry só com o necessário para a escolha do dominante."""
    def __init__(self, pk, quantity):
        self.pk = pk
        self.quantity = quantity


def run():
    ck = rc.category_key

    check("self_check vazio", rc.self_check() == [])
    check("recount_total == 699", rc.recount_total() == 699)
    check("19 categorias", len(rc.RECOUNT_039) == 19)

    # category_key
    check("eMCP 8+1", ck(chip_type="eMCP", emcp_nand="eMMC 8GB", emcp_ram="LPDDR 1GB", is_emcp=True) == "EMCP 8+1")
    check("eMCP 16+1.5", ck(chip_type="eMCP", emcp_nand="eMMC 16GB", emcp_ram="LPDDR 1.5GB", is_emcp=True) == "EMCP 16+1.5")
    check("LPDDR4X -> D4", ck(chip_type="LPDDR4X", capacity="4GB", interface="LPDDR4X") == "D4 4GB")
    check("LPDDR3 -> D3", ck(chip_type="LPDDR3", capacity="3GB", interface="LPDDR3") == "D3 3GB")
    check("eMMC", ck(chip_type="eMMC", capacity="16GB") == "EMMC 16GB")
    check("UFS", ck(chip_type="UFS", capacity="64GB") == "UFS 64GB")
    check("uMCP fora do recount", str(ck(chip_type="uMCP", emcp_nand="128GB", emcp_ram="8GB", is_emcp=True)).startswith("UMCP"))
    check("sem capacidade -> None", ck(chip_type="LPDDR4", capacity="", interface="LPDDR4") is None)

    # vazio
    p = rc.compute_reconciliation({})
    check("vazio to_add 699", p["totals"]["to_add"] == 699)
    check("vazio todas add", all(r["action"] == "add" for r in p["rows"]))

    # parcial (números reais aproximados da produção)
    existing = {"EMCP 8+1": 218, "EMCP 16+2": 83, "UFS 64GB": 8, "D4 3GB": 3}
    byk = {r["key"]: r for r in rc.compute_reconciliation(existing)["rows"]}
    check("8+1 delta 25 add", byk["EMCP 8+1"]["delta"] == 25 and byk["EMCP 8+1"]["action"] == "add")
    check("16+2 delta 13 add", byk["EMCP 16+2"]["delta"] == 13)
    check("UFS 64 delta 1", byk["UFS 64GB"]["delta"] == 1)
    check("D4 3GB ok", byk["D4 3GB"]["delta"] == 0 and byk["D4 3GB"]["action"] == "ok")

    # over + extras
    p = rc.compute_reconciliation({"UFS 64GB": 20, "UMCP 128+6": 2})
    byk = {r["key"]: r for r in p["rows"]}
    check("UFS over -11", byk["UFS 64GB"]["delta"] == -11 and byk["UFS 64GB"]["action"] == "over")
    check("extra uMCP", p["extras"] == {"UMCP 128+6": 2})

    # idempotência: sistema == físico -> nada
    full = {key: qty for key, qty in rc.RECOUNT_039}
    p = rc.compute_reconciliation(full)
    check("idempotente to_add 0", p["totals"]["to_add"] == 0)
    check("idempotente tudo ok", all(r["action"] == "ok" for r in p["rows"]))

    # regra "chip dominante" (mesma do command): maior quantidade, desempate maior pk
    cands = [FakeEntry(pk=1, quantity=10), FakeEntry(pk=2, quantity=40), FakeEntry(pk=3, quantity=40)]
    chosen = max(cands, key=lambda e: (e.quantity, e.pk))
    check("dominante = maior qtd, desempate maior pk", chosen.pk == 3 and chosen.quantity == 40)

    print("\nRESULTADO:", "TODOS OK" if not fails else f"{len(fails)} FALHA(S): {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run())
