# ⚠ PLANILHA, NUNCA BANCO (2026-09-20). Este script serve para OLHAR a largura
#   dos K4B, não para gravá-la. A largura de catálogo mora em `KnownPart.bus_width`
#   (era `interface` até 2026-09) e só entra por fonte Tier-1 da marca —
#   datasheet ou decodificador oficial de part number — pelo `submit_known_parts
#   --fill-empty`. Decodificar o PN aqui e escrever no banco é a circularidade do
#   HANDOFF_largura_barramento.md §3: a regra passa a concordar com ela mesma.
from chips.models import KnownPart
import csv

qs = (KnownPart.objects
      .filter(brand__name="Samsung", part_number__startswith="K4B", review_status="approved")
      .order_by("part_number"))

rows = []
for kp in qs:
    base = kp.part_number.split("-")[0]
    if len(base) < 7:
        continue
    largura = base[5:7]
    if largura in ("04", "08"):
        rows.append([kp.part_number, base[3:5], "x4" if largura == "04" else "x8", kp.confidence])

with open("k4b_x4_x8_producao.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["part_number", "densidade", "largura", "confidence"])
    w.writerows(rows)

print(f"{len(rows)} PNs gravados em k4b_x4_x8_producao.csv")
