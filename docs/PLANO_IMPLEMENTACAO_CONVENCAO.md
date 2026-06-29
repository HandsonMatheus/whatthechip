# PLANO DE IMPLEMENTAÇÃO — Convenção única de tipos de chip (WTC)

> **Runbook de execução** — escrito para o agente seguir, fase a fase.
> Criado 2026-06-29. Decisão **travada: opção 1** (geração no `chip_type`,
> espelhada no `subtype`). Insumos: `docs/BRIEFING_CONVENCAO_TIPOS_CHIP.md`
> (contrato dos consumidores) + `docs/CARACTERIZACAO_BASELINE.md` (estado real
> dos 7.021 registros). Backup pré-refactor: `wtc_backup_pre-convencao_20260629.tar.gz`
> (sha256 `491db79e…`).
>
> **Como usar:** seguir as fases na ordem. Cada fase tem *objetivo · arquivos ·
> quem roda · verificação · rollback*. Não pular a verificação. **Não avançar de
> fase com teste vermelho que não seja o contrato (fase 2+) esperado.**

---

## 0. Decisão travada e princípios inegociáveis

1. **Opção 1.** Para DRAM discreta, a geração mora no `chip_type` (`DDR3`,
   `LPDDR4X`, `GDDR5`) e é **espelhada** no `subtype`. Memória gerenciada
   (eMMC/UFS/eMCP/uMCP/NAND) mantém o `chip_type` atual; só limpa o `subtype`.
   Justificativa decisiva: `InventoryEntry` persiste `chip_type`, **não** `subtype`
   nem `dram_density` → a geração só sobrevive na linha salva e no Excel se estiver
   no `chip_type`. Dados confirmam: 4.867/4.868 das gerações são recuperáveis.
2. **Fonte única.** Toda a convenção vive em `chips/chip_types.py`. Gateway,
   rentabilidade, validador, populate e docs **leem dela** — nada de regra
   duplicada por marca. Mesma filosofia de `canonical_gen`/`assess_profitability`.
3. **Refactor preserva comportamento.** As fases de código (2–3) **não mudam
   label nem veredito de rentabilidade** — só trocam o *despacho* por substring
   por *despacho pelo registro*. Provado pela rede de regressão (saída idêntica
   antes/depois). **Única exceção decidida (2026-06-29):** `SDRAM` e `RDRAM`
   passam a `NÃO RENTÁVEL` por tipo (§2.1) — a rede de regressão declara essa
   mudança como esperada. Outras mudanças de veredito ficam fora do escopo.
4. **Mudanças aditivas no dict de resultado.** O site serializa o dict inteiro
   (`/chips/search/`). **Nunca renomear/remover chave** de `classify()`; só
   adicionar. (`chip_type` muda de *valor*, não de chave — ok.)
5. **Claude edita; o usuário roda comandos de DB** (`populate_*`, `migrate`,
   `normalize_convention`). Sempre `--dry-run` antes; idempotente; reversível
   por JSON. **Reiniciar o servidor após `populate_* --overwrite`** (cache
   `lru_cache` do engine).
6. **Nunca rebaixar `confirmed`/`manual`.** A migração só normaliza
   `chip_type`/`subtype`/PN; preserva `confidence` e specs.
7. **Escopo.** **DENTRO:** convenção de `chip_type`/`subtype`, alinhamento dos
   `populate_*`, migração reversível, testes. **FORA (passo próprio, com aprovação
   explícita do usuário):**
   - **Normalização de PN** (`:`/`.`/`_`) — auditada 2026-06-29: **segura** (0
     regressões, 96 testes verdes) mas **grande e sensível** (3.731 registros, quase
     todos Micron; **975 chips passariam de aprovado→descarte**). Separada da convenção
     por isso e por estar entrelaçada com os dados Micron. Revertida do refactor; será
     feita como passo próprio, com o usuário revisando os 975 antes de ligar.
   - Preenchimento de specs Micron (3.805 sem capacidade — tarefa de dados).
   - Campo `generation` dedicado (opção 2, evolução futura — o registro a torna barata).
   - Mudar vereditos de rentabilidade (exceto SDRAM/RDRAM/EDO DRAM, já decididos).

---

## 1. Arquitetura alvo — fonte única

```
                       chips/chip_types.py   ← A FONTE ÚNICA (novo)
                       (vocabulário fechado + esquema por tipo)
                                 │ lê
       ┌─────────────┬──────────┼───────────────┬───────────────┐
       ▼             ▼          ▼                ▼               ▼
 _compute_destination  assess_     validate_      populate_*/    docs
 (estoque/views)       profitability convention   normalize_*    (gerados)
 label da caixa        (engine)    (novo cmd)     (write-time)
```

`chip_types.py` expõe (proposto):

- `CHIP_TYPES: dict[str, ChipTypeSpec]` — o registro. Chave = token canônico.
- `ChipTypeSpec`: `category`, `label_kind`, `profit_family`, `commercial`,
  `carries_generation`, `aliases`.
- `canonical_chip_type(raw_chip_type, subtype="") -> str` — normaliza qualquer
  string ao token canônico (ou genérico flagged). Reusa `canonical_gen`.
- `spec_for(chip_type) -> ChipTypeSpec | None`.
- `is_commercial(chip_type) -> bool`, `profit_family(chip_type) -> str`,
  `label_kind(chip_type) -> str`.

**Adicionar marca/tipo novo (CPU, DDR6, UFS 4.x) = uma entrada em `CHIP_TYPES`.**
É a propriedade de escala: vocabulário declarado uma vez, validado no write-time,
lido em todo lugar.

---

## 2. A convenção canônica (a especificação)

### 2.1 Vocabulário fechado de `chip_type`

**Memória gerenciada — geração NÃO vai no `chip_type`:**

| `chip_type` | categoria | `label_kind` | rentab. | comercial | `subtype` canônico | `is_emcp` |
|---|---|---|---|---|---|---|
| `eMMC` | managed_nand | `EMMC{cap}` | emmc | sim | `""` (versão→`interface`) | não |
| `UFS` | managed_nand | `UFS{cap}` | ufs | sim | `""` | não |
| `eMCP` | managed_mcp | `EMCP{nand}+{ram}` | emcp | sim | geração LPDDR (`"LPDDR4X"`) | sim |
| `uMCP` | managed_mcp | `UMCP{nand}+{ram}` | emcp | sim | geração LPDDR | sim |
| `NAND Flash` | nand_raw | `{cell} {cap}` | dead* | sim | célula (`"SLC NAND"`…) | não |

**DRAM discreta — geração VAI no `chip_type` + espelho no `subtype`:**

| `chip_type` | categoria | `label_kind` | rentab. | `subtype` |
|---|---|---|---|---|
| `DDR1` `DDR2` `DDR3` `DDR3L` `DDR4` `DDR5` | dram_pc | `{gen}+{Gb}G` (die) | ddr | espelho |
| `LPDDR1` `LPDDR2` `LPDDR3` `LPDDR4` `LPDDR4X` `LPDDR5` `LPDDR5X` | dram_mobile | `{gen}+{GB}GB` (pacote) | lpddr | espelho |
| `GDDR2` `GDDR3` `GDDR5` `GDDR6` `GDDR6X` | dram_gpu | `{gen}+{Gb}G` | gddr | espelho |
| `SDRAM` (SDR, anterior ao DDR1) | dram_legacy | `SDRAM+{Gb}G` | dead* | `"SDRAM"` |
| `RDRAM` (Rambus, arquitetura à parte) | dram_legacy | `RDRAM` | dead* | `"RDRAM"` |

**Catálogo — sem caixa comercial; classificação/documentação só:**

| `chip_type` | rentab. | nota |
|---|---|---|
| `NOR Flash` `OneNAND` `MCP` `ePoP` | dead* | sucata/empilhado, sem mercado B2B |
| `SoC` `PMIC` `Sensor` `SRAM` `Mask ROM` `NVMe SSD` `BGA SSD` `EDO DRAM` | indeterminado | catálogo, sem caixa |

\* **dead** = sempre `NÃO RENTÁVEL` por tipo. Hoje: `nand flash`/`nor flash`/`mcp`/
`epop`; **passa a incluir `SDRAM` e `RDRAM`** (decisão 2026-06-29: SDR e Rambus são
anteriores/obsoletos ao DDR1, já abaixo do mínimo DDR3 → sucata). Match **exato** no
token canônico de `chip_type` (não substring) — para não pegar `subtype` `"DDR3 SDRAM"`,
que é DDR3 e rentável. Catálogo (`SoC`/`PMIC`/`EDO DRAM`/…) segue `INDETERMINADO`
(comportamento atual preservado; rever depois é decisão de negócio).

**Tokens genéricos transicionais** (`DDR`, `LPDDR`, `GDDR`, `RAM`, `DRAM`):
válidos no vocabulário **mas sinalizados pelo `validate_convention`** como
"geração ausente — confirmar". Servem só às famílias genuinamente multi-geração
até a confirmação por PN. Meta: **zero** ao fim, exceto famílias ambíguas.

### 2.2 Esquema de campos (o que carrega o quê) — **regra de unidade inviolável**

> **die em `Gb` (gigabit), pacote em `GB` (gigabyte). 1 GB = 8 Gb. Nunca trocar.**

| Campo | Quem usa | Unidade |
|---|---|---|
| `capacity` | eMMC, UFS, LPDDR (pacote), NAND raw | GB/TB (LPDDR/eMMC/UFS), MB/GB (NAND) |
| `density_gbit` / `dram_density` | DDR, GDDR, SDRAM (die) | Gb |
| `emcp_nand` / `emcp_ram` | eMCP, uMCP | GB (`"LPDDR4X 4GB"`, `"eMMC 5.1 64GB"`) |
| `subtype` | DRAM→geração; eMCP/uMCP→geração LPDDR; eMMC/UFS→`""`; NAND→célula | — |
| `interface` | bus width DDR/GDDR (`x8`/`x16`); versão eMMC/UFS | — |
| `tip`/`notes` | resto (tensão, temperatura, organização, ECC) | — |

### 2.3 Regras de borda (decididas)

1. **Famílias multi-geração** (Samsung `K3` LPDDR2/3; SanDisk `SDEM` LPDDR3/4):
   `ChipFamily.chip_type` = token genérico (`"LPDDR"`) **flagged**; `KnownPart`
   confirmado deve ser específico (`"LPDDR3"`). Validador alerta, não bloqueia.
2. **`DDR3L`** é token próprio (distinção real de label/tensão). `canonical_gen`
   já trata.
3. **Tokens-lixo** (~15 registros: `EDO DRAM`, `GDDR SDRAM`, `DDR4 SDRAM`, `DRAM`,
   `Appliance Part`, `SoC`, 12 vazios) → lista de canonicalização manual na
   migração (mapa explícito PN→tipo, ou `confidence` rebaixado se for sucata).
4. **Normalização de marca:** `KIOXIA`→`Kioxia`, e qualquer casing duplicado →
   forma canônica única (passo no `normalize_convention`).
5. **Normalização de PN** (3.898 registros com `:`/`.`/`_`): estender o fallback
   normalizado do engine (`classify`, bloco 1a′) para remover **também** `:`,
   `.`, `_` (hoje só remove `-` e espaço). Os únicos ofensores no banco são esses
   três → 3 `Replace()` extras resolvem, DB-agnóstico. Write-time: normalizar PN
   nos `populate_*`/import. (Não reescrever PNs existentes nesta fase — o fix de
   lookup já os torna encontráveis.)

---

## 3. Estratégia de testes (a rede de segurança)

Rodar sempre com `--settings=core.settings_test` (SQLite). Carga de dados reais
via `prod_data.json` (fixture) num teste dedicado.

### 3.1 Rede de regressão — *trava o comportamento atual* (verde agora)
- **Golden snapshot:** o `char_records.jsonl` (7.021 PNs → `classify` + label +
  rentabilidade) vira o baseline esperado, commitado como fixture reduzida
  (ou hash por PN). Teste re-roda o pipeline e exige:
  - **campos NÃO tocados pela convenção** (capacity, emcp_*, profitable, label
    de gerenciada) → **idênticos**;
  - **campos da convenção** (chip_type/subtype/label DRAM) → mudança **esperada**
    (ex.: `RAM`→`DDR3`, label `x16+64G`→`DDR3+...`) declarada por asserção.
- **Spot-checks legíveis por marca:** 1 PN representativo por família (Samsung
  DDR/LPDDR/GDDR/eMCP, Hynix DDR/eMCP/GDDR, Micron MCP/LPDDR, PieceMakers,
  GigaDevice, Kingston, SanDisk, Toshiba/Kioxia, Rayson, Nanya) → asserção
  explícita do resultado. Falha aponta o chip exato.

### 3.2 Contrato da convenção — *o alvo* (vermelho → verde)
- `chip_types.py`: todo token atual mapeia a um canônico ou genérico-flagged;
  `canonical_chip_type` é idempotente; vocabulário cobre as 14 marcas.
- `_compute_destination` produz o label certo por tipo canônico (eMMC/UFS/eMCP/
  uMCP/NAND/DDR/LPDDR/GDDR) — casos de mesa.
- `assess_profitability` idêntica ao baseline por tipo (reproduz o atual).
- `validate_convention` retorna **zero não-conformes** após a migração.

### 3.3 Suíte existente (68 testes)
- Rodar antes (baseline verde). Atualizar os que codificam o dialeto antigo
  (`chip_type="RAM"`) para a forma canônica. Manter verde ao fim.

**Comando único de verificação:** `python manage.py test chips estoque --settings=core.settings_test`

---

## 4. Fases de execução (o passo a passo)

### Fase 0 — Rede de segurança ✅ FEITO
Backup completo verificado. (Task #6.)

### Fase 1 — Baseline verde
- **Objetivo:** provar que o sistema atual está verde antes de tocar nele.
- **Arquivos:** nenhum (só rodar).
- **Quem roda:** Claude (sandbox, SQLite).
- **Verificação:** `test chips estoque` passa; `characterize.py` re-roda sem erro;
  snapshot `char_records.jsonl` salvo como golden.
- **Rollback:** n/a.

### Fase 2 — Definir a convenção (`chip_types.py`) + contrato
- **Objetivo:** a fonte única, **sem mudar comportamento ainda**.
- **Arquivos:** `chips/chip_types.py` (novo); `chips/tests_convention.py` (novo,
  contrato §3.2 — começa vermelho onde descreve o alvo do refactor).
- **Quem roda:** Claude.
- **Verificação:** contrato do registro (vocabulário/idempotência) verde; o resto
  do contrato vermelho-esperado. Apresentar `chip_types.py` ao usuário p/ revisão.
- **Rollback:** deletar os 2 arquivos (não tocou em nada existente).

### Fase 3 — Refatorar consumidores (preserva saída) + normalização de PN
- **Objetivo:** gateway e rentabilidade despacham pelo registro; lookup de PN
  robusto. **Zero mudança de label/veredito** vs. baseline.
- **Arquivos:** `estoque/views.py` (`_compute_destination` → `label_kind`;
  `gen = canonical_gen(subtype) or canonical_gen(chip_type) or interface`);
  `chips/engine.py` (`assess_profitability` → `profit_family`; fallback de PN
  com `:`/`.`/`_`).
- **Quem roda:** Claude.
- **Verificação:** **rede de regressão idêntica** nos campos não-convenção; suíte
  existente verde. Re-rodar `characterize.py` e *diff zero* fora dos campos de
  convenção.
- **Rollback:** reverter os 2 arquivos (git); backup disponível.

### Fase 4 — Alinhar os `populate_*` (write-time)
- **Objetivo:** dados novos nascem canônicos.
- **Arquivos:** `populate_samsung/hynix/micron_mcp/piecemakers/gigadevice/
  kingston/sandisk/toshiba/rayson.py`; cobrir **Nanya/AMD/Kioxia** (sem populate
  hoje); `chips/conventions.py` se precisar estender `canonical_gen`.
- **Quem roda:** Claude edita; **usuário roda** `populate_* --dry-run` depois
  `--overwrite`; **reinicia o servidor**.
- **Verificação:** após cada populate, `validate_convention` na marca → conforme;
  spot-checks da marca verdes.
- **Rollback:** `populate_* --overwrite` é idempotente; backup; git nos arquivos.

### Fase 5 — Migração de dados (`normalize_convention`)
- **Objetivo:** os ~4.465 KnownParts genéricos → forma canônica; junk + casing.
- **Arquivos:** `chips/management/commands/normalize_convention.py` (novo).
- **Quem roda:** Claude escreve; **usuário roda** `--dry-run` → revisa →
  `--commit` (grava JSON reversível) → **reinicia o servidor**.
- **Lógica:** para cada KnownPart DRAM genérico, `chip_type = canonical_gen(
  subtype||chip_type)`; espelha no `subtype`; aplica mapa de junk; normaliza
  marca; **preserva** `confidence`/specs. Idempotente.
- **Verificação:** `validate_convention` global → **zero não-conformes** (fora os
  genéricos-flagged ambíguos); re-rodar `characterize.py` → distribuição de
  `chip_type` = a "proposta" do baseline.
- **Rollback:** `normalize_convention --revert <json>`; backup.

### Fase 6 — Validação final (estoque + rentabilidade + identificação)
- **Objetivo:** provar as três funcionalidades ponta a ponta.
- **Arquivos:** nenhum (rodar) + `docs/` (relatório antes/depois).
- **Quem roda:** Claude (suíte) + usuário (sanity no servidor real).
- **Verificação:** `test chips estoque` 100% verde (existentes + regressão +
  contrato); `validate_convention` zero; relatório antes/depois confirmando
  label/rentabilidade/identificação por marca.
- **Rollback:** backup (cenário catastrófico).

---

## 5. Ordem dos comandos que o USUÁRIO roda (resumo)

```bash
# Fase 4 — por marca (exemplo)
python manage.py populate_samsung --dry-run
python manage.py populate_samsung --overwrite      # depois de revisar
#   …repetir para cada marca… → REINICIAR o servidor

# Fase 5 — migração dos confirmados
python manage.py normalize_convention --dry-run     # revisar o diff
python manage.py normalize_convention --commit       # grava JSON reversível
#   → REINICIAR o servidor
python manage.py validate_convention                 # deve dar 0 não-conformes

# rollback de dados, se preciso
python manage.py normalize_convention --revert normalize_convention_revert.json
```

> Lembrar: **DATABASE_URL apontando ao banco certo**; `--dry-run` sempre antes;
> **reiniciar o servidor** após cada `--overwrite`/`--commit` (cache do engine).

---

## 6. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Refactor muda label/veredito sem querer | Rede de regressão exige diff zero nos campos não-convenção (fase 3) |
| Migração corrompe `confirmed`/`manual` | `normalize_convention` só toca chip_type/subtype/PN; preserva confidence/specs; reversível |
| Cache velho serve gramática antiga | Reiniciar servidor após cada `--overwrite`/`--commit` (regra de ouro #3) |
| Site/JSON quebra (chave renomeada) | Só mudança aditiva; `chip_type` muda valor, não chave; teste de serialização |
| Família multi-geração vira tipo errado | Token genérico flagged; confirmado por PN; validador alerta |
| PN com `:`/`.` continua sumindo | Fix do fallback (fase 3) coberto por teste de lookup |
| Marca nova futura foge da convenção | `validate_convention` no CI/manual barra; adicionar 1 entrada no registro |

---

## 7. Critérios de aceite (definition of done)

1. `python manage.py test chips estoque --settings=core.settings_test` → **100% verde**
   (existentes atualizados + regressão + contrato).
2. `validate_convention` → **0 não-conformes** (exceto genéricos-flagged ambíguos documentados).
3. `characterize.py` pós-migração → distribuição de `chip_type` = a "proposta"
   do baseline; **diff zero** nos campos não-convenção vs. baseline.
4. As três funcionalidades verdes por marca: **identificação** (chip_type/subtype
   corretos), **estoque** (label da caixa correto + persistência), **rentabilidade**
   (veredito idêntico ao baseline).
5. Docs unificados: `CONVENCAO_CAMPOS_ESTOQUE.md` reescrito p/ opção 1; `CLAUDE.md §6`
   + `<MARCA>.md §2` apontando a tabela canônica única (resolve a contradição §8.5).

---

## 8. Checklist sequencial

- [ ] **F0** Backup verificado ✅
- [ ] **F1** Baseline verde (suíte + characterize) e golden salvo
- [ ] **F2** `chip_types.py` escrito + contrato (registro verde) + **revisão do usuário**
- [ ] **F3** Refactor gateway + rentabilidade + normalização PN → regressão diff-zero
- [ ] **F4** `populate_*` alinhados (todas as marcas + Nanya/AMD/Kioxia) → usuário roda → restart
- [ ] **F5** `normalize_convention` (dry-run → commit) → usuário roda → restart → validador 0
- [ ] **F6** Validação final + relatório antes/depois + docs unificados

---

## Anexo — mapa de arquivos

| Arquivo | Fase | Ação |
|---|---|---|
| `chips/chip_types.py` | 2 | **novo** — a fonte única |
| `chips/tests_convention.py` | 2 | **novo** — contrato |
| `chips/tests_regression.py` | 1/3 | **novo** — golden 7.021 |
| `estoque/views.py` | 3 | `_compute_destination` → registro |
| `chips/engine.py` | 3 | `assess_profitability` → registro; fallback PN `:`/`.` |
| `chips/conventions.py` | 3/4 | estender `canonical_gen` se preciso |
| `chips/management/commands/populate_*.py` | 4 | emitir forma canônica |
| `chips/management/commands/validate_convention.py` | 2/6 | **novo** — portão |
| `chips/management/commands/normalize_convention.py` | 5 | **novo** — migração reversível |
| `docs/CONVENCAO_CAMPOS_ESTOQUE.md`, `CLAUDE.md`, `<MARCA>.md` | 6 | unificar p/ opção 1 |
