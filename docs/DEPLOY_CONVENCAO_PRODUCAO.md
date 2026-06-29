# DEPLOY — Convenção de tipos em PRODUÇÃO (runbook)

> Runbook de aplicação em produção. **Nada aqui foi rodado ainda** — todo o trabalho
> até agora foi numa cópia descartável (fixture do `prod_data.json`); produção está
> intocada. Rode **top-to-bottom** quando tudo estiver pronto. Cada comando de banco
> tem **dry-run → revisar → aplicar**. Idempotente (pode repetir).
>
> Backup pré-refactor: `wtc_backup_pre-convencao_20260629.tar.gz` (sha256 `491db79e…`).

---

## Como rodar comando no banco de PRODUÇÃO

Os comandos `manage.py` agem sobre o banco apontado por `DATABASE_URL`. Para mexer na
produção, use **seu método habitual** (um dos dois):

- **Local apontando ao Render:** `DATABASE_URL="<postgres do Render>" python manage.py <cmd>`
- **Shell do Render:** abrir o shell do serviço web no dashboard e rodar lá.

**"Reiniciar o servidor"** = restart/redeploy do serviço web no Render — limpa o cache
`lru_cache` do engine (regra de ouro #3). Obrigatório após `populate_*`/migração.

⚠ Sempre `--dry-run` antes, onde existir.

---

## Fase 0 — Pré-voo
- [ ] Backup guardado **fora** do projeto (HD externo / nuvem).
- [ ] (recomendado) Snapshot fresco do banco agora:
      `DATABASE_URL=<render> python manage.py dumpdata chips estoque > prod_pre_convencao.json`

## Fase 1 — Deploy do CÓDIGO
O refactor **preserva comportamento** (provado: 6 diffs intencionais em 7.021 registros,
96 testes verdes) e é compatível com o dado antigo — seguro deployar antes da migração.
- [ ] `git add -A`
- [ ] `git commit -m "Convenção única de tipos (chip_types.py) + refactor consumidores + pendências Samsung/Micron/Kingston"`
- [ ] `git push origin main` → Render auto-deploy.
- [ ] Verificar: deploy verde no Render; site no ar.

**Vai no deploy:** `chips/chip_types.py` (novo), `chips/engine.py` (rentab.→registro),
`estoque/views.py` (label→registro), `validate_convention.py` (novo),
`tests_convention.py` (novo), `fix_known_parts.py` (8 entradas Micron),
`populate_samsung.py` (família K4RC + `DRAM_PC['CH']`).

## Fase 2 — Dados: pendências confirmadas tier-1

### 2.1 Samsung
- [ ] Remover lixo `DA97`:
      `python manage.py shell -c "from chips.models import KnownPart; print(KnownPart.objects.filter(part_number='DA97').delete())"`
- [ ] `python manage.py populate_samsung --dry-run` → revisar
- [ ] `python manage.py populate_samsung --overwrite`  *(aplica família K4RC + `DRAM_PC['CH']`)*
- [ ] **Reiniciar o servidor.**
- [ ] Verificar no site: `K4RCH046VM` → **DDR5 4GB**.

### 2.2 Micron
- [ ] `python manage.py fix_known_parts --dry-run` → revisar
- [ ] `python manage.py fix_known_parts`  *(3× MC SLC NAND 512MB · 4× MT42L LPDDR2 1.5GB · MT41K DDR3L)*
- [ ] **Reiniciar.**
- [ ] Verificar: FBGA `D9RRD` → **LPDDR2 1.5GB**; `MT41K64M16TW` → **DDR3L**.

### 2.3 Kingston *(os 7 eram Samsung mal-rotulados)*
- [ ] Remover os 7:
      `python manage.py shell -c "from chips.models import KnownPart; print(KnownPart.objects.filter(part_number__in=['KFG1G16U2C','KFG1GN6W2D','KFG1GNGW2D','KFM4G16Q4B','KFC1G16U2C','KFMNX0012M','KFFN60012M']).delete())"`
- [ ] **Operador:** reler o chip físico de `KFMNX0012M` / `KFFN60012M` — real = `KMFNX0012M` / `KMFN60012M` (Samsung, com valor).
- [ ] Famílias bogus `KF`/`KVR`/`ACR` já saem **desativadas** pelo `add_chip_families`
      (Fase 1) + `normalize` (Fase 3) — nada a fazer aqui.
- [ ] **Reiniciar.**

## Fase 3 — Alinhamento das famílias + migração mecânica — ✅ PRONTO
> Os `populate_*` e o `add_chip_families` já nascem CANÔNICOS (`chip_type` = geração);
> o `normalize_convention` migra ~4.454 KnownParts + famílias e desativa as bogus.
> **A ordem importa: rode os populate ANTES do normalize.** Verificado na fixture: 190
> famílias conforme · 0 migrar (só K3 = multi-geração genérico, esperado); KnownParts
> migrar=0; comportamento (label/rentab.) preservado.
- [ ] Garantir que os populate canônicos rodaram (Fase 2 + `add_chip_families --overwrite`).
- [ ] `python manage.py normalize_convention --dry-run` → revisar o diff (chip_type RAM→geração)
- [ ] `python manage.py normalize_convention --commit`  *(grava JSON reversível)*
- [ ] **Reiniciar.**
- [ ] `python manage.py validate_convention` → só os 13 já deletados/corrigidos (→ 0).

## Fase 4 — Validação pós-deploy
- [ ] `python manage.py validate_convention` → conforme.
- [ ] Spot-check no site por marca (DDR3, LPDDR4X, eMCP, NAND…).
- [ ] Export `.xlsx` do estoque: a **geração aparece** (`DDR4`, não `RAM`).

## Rollback
- **Código:** `git revert <commit> && git push`.
- **Dados:** `python manage.py normalize_convention --revert <json>`; ou restore do
  snapshot (`prod_pre_convencao.json`) / do backup completo.

---

### Estado (atualizo conforme avanço)
| Fase | Pronto? |
|---|---|
| 1. Código (refactor + pendências + populate canônicos) | ✅ pronto |
| 2.1 Samsung | ✅ pronto |
| 2.2 Micron | ✅ pronto |
| 2.3 Kingston (deletes + bogus desativadas) | ✅ pronto |
| 3. Famílias + migração (normalize_convention) | ✅ pronto e provado |

### ⚠ Mudanças de comportamento intencionais (esperadas pós-deploy)
- **+277 chips Micron LPDDR4/4X** deixam de ser descartados (bug `_lpddr_generation`:
  genérico tratado como LPDDR1). Passam a INDETERMINADO → aprovados p/ conferência.
- **EDO DRAM / SDRAM / RDRAM** → sempre NÃO RENTÁVEL (sucata, anteriores ao DDR1).
- **chip_type** no card/Excel passa a mostrar a geração (`DDR4`) em vez de `RAM`.
