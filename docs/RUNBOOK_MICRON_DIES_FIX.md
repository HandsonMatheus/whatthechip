# RUNBOOK — Aplicar a correção do bug de dies Micron (produção)

> **O quê:** o bug de dies inflava a capacidade Micron LPDDR (`depth × width × dies ÷ 8`
> em vez de `÷ 8`). O CÓDIGO já está corrigido (engine `decode_density_type='micron'`,
> famílias com geração canônica, `fix_micron_lpddr_specs`). Falta aplicar os DADOS em
> produção. Ver `MICRON.md §5/§14/§15` para o contexto técnico.
>
> **Regra de ouro #1:** o usuário roda; o agente só edita arquivos. **#3:** reiniciar o
> servidor após mexer em dados (cache `lru_cache` do engine).

---

## Ordem (importa!)

O código tem que estar **deployado** antes de rodar os comandos de dados no Render —
senão `fix_micron_lpddr_specs` nem existe lá, e `add_chip_families --overwrite` usaria o
seed antigo (MT52L errado como LPDDR4).

```
local: aplicar dados  →  commit  →  push  →  Render deploya  →  Render: aplicar dados  →  restart
```

---

## 1. Local (o código já está no working tree)

```bash
python manage.py add_chip_families --overwrite        # famílias: chip_type/subtype/flag
python manage.py fix_micron_lpddr_specs --dry-run      # revisar a lista (1228 esperados)
python manage.py fix_micron_lpddr_specs                # aplicar
# reiniciar o runserver
```

## 2. Commit + push

```bash
git push        # dispara o auto-deploy no Render
```

## 3. Render — SÓ DEPOIS do deploy terminar (shell do serviço)

```bash
python manage.py add_chip_families --overwrite
python manage.py fix_micron_lpddr_specs --dry-run      # confere os números
python manage.py fix_micron_lpddr_specs                # aplica
```
Depois **reiniciar o serviço web do Render** (Dashboard → Manual Deploy → "Restart"
ou "Clear build cache & deploy"). O cache do engine não se limpa sozinho no processo web.

---

## 4. Verificação (shell novo, em CADA banco)

```bash
python manage.py shell -c '
from chips.engine import classify
for pn in ["D9WLQ","D9WRQ","D9QRP","D9WGH"]:
    r=classify(pn); print(pn,"->",r.get("capacity"),"|",r.get("chip_type"),"|",r.get("subtype"))'
```

Esperado nos dois bancos:

| FBGA | esperado |
|---|---|
| D9WLQ (MT53E1G32D4NQ) | `4 GB \| LPDDR4X \| LPDDR4X` |
| D9WRQ (MT53E768M32D4DT) | `3 GB \| LPDDR4X \| LPDDR4X` |
| D9QRP (MT52L128M32D1EL) | `512 MB \| LPDDR3 \| LPDDR3` |
| D9WGH (MT53D512M64D4RQ) | `4 GB \| LPDDR4 \| LPDDR4` |

Auditoria opcional (deve dar `0` divergências de capacidade em toda DRAM+eMMC):

```bash
python manage.py shell -c '
import re
from collections import Counter
from chips.models import KnownPart
def norm(s): return (s or "").replace(" ","").upper()
DRAM = re.compile(r"^MT\d{2}[A-Z]+?(\d+)([MG])(\d+)", re.I)
EMMC = re.compile(r"^MTF[CD](\d+)G", re.I)
def expect(pn):
    c=pn.split("-")[0].split(" ")[0].upper(); m=DRAM.match(c)
    if m:
        r,u,b=int(m.group(1)),m.group(2).upper(),int(m.group(3)); gb=r*(1024 if u=="G" else 1)*b/8/1024
        return f"{int(gb)}GB" if gb==int(gb) else (f"{gb:.1f}GB" if gb>=1 else f"{int(round(gb*1024))}MB")
    m=EMMC.match(c); return f"{m.group(1)}GB" if m else None
mis=tot=0
for pn,cap in KnownPart.objects.filter(brand__name="Micron",confidence__in=["confirmed","manual"]).values_list("part_number","capacity"):
    e=expect(pn)
    if e and cap: tot+=1; mis+= (norm(cap)!=norm(e))
print("capacidade divergente:", mis, "de", tot)'
```

---

## Notas

- `fix_micron_lpddr_specs` é **idempotente** e tem `--dry-run`. Não toca `confidence`,
  `part_number` nem `fbga_code`. Guard: pula eMCP real (`emcp_nand`/`emcp_ram` não-vazios).
- `add_chip_families --overwrite` re-semeia **todas** as 39 famílias (reseta tip/subtype
  pro código — NÃO toca `decode_cap_pos`/maps das outras marcas).
- Backlog (não bloqueia, ver `MICRON.md §15`): 251 PNs `-DC`, estender o flag micron às
  DDR/LPDDR5, completude (MT47H/MT63G/eMCP vazios), auditoria fina do eMCP.
