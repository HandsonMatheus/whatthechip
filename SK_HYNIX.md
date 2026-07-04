> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da SK Hynix (famílias + decode maps) vive em
> **`chips/knowledge/hynix.yaml`** (via `load_brands`). Os **known_parts** (PNs confirmados = autoridade)
> **NÃO ficam mais no yaml** — vivem no **banco**, submetidos por `submit_known_parts` e **aprovados pelo
> dono** no admin (four-eyes). **Processo obrigatório completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados (decode key→valor, inventário de famílias):
> esses vivem no **yaml** (gramática) e no **banco** (known_parts). Aqui ficam: **convenções, anatomia do
> PN, armadilhas, rentabilidade, fontes, o *porquê*** e ponteiros.

---

# SK_HYNIX.md — Bíblia Técnica e de Negócio

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/hynix.yaml`). Regras gerais do WTC: `CLAUDE.md`.

SK Hynix é o **2º maior fabricante global de DRAM** (depois da Samsung) e grande fornecedor de NAND.
Na bancada da eMiner é a **2ª marca mais frequente**, forte em LPDDR mobile e DDR de PC. O yaml tem
**~36 famílias** (DDR1→DDR5, GDDR3, LPDDR1→5X, eMMC, UFS, eMCP/uMCP) — a lista viva está no yaml.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/hynix.yaml   ← GRAMÁTICA (famílias + decode maps). SÓ isso (Opção 2).
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml)
AUTORIA.md / CLAUDE.md §5     ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → edita o yaml → `load_brands
--brand hynix` (dry-run = portão) → o **dono** roda `--commit`. **known_parts** (autoridade) →
`submit_known_parts` (dry-run) → o **dono** roda `--commit` + **aprova no admin**. ⚠ **Família nova → PN-âncora
no golden é OBRIGATÓRIO** (`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:** `chips/engine.py`,
`estoque/views.py` (globais), yamls/known_parts de outras marcas, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca `load_brands --commit`/`migrate` sem confirmação.
2. **`load_brands --brand hynix` (dry-run) é o portão** — valida a convenção, nada gravado. Depois `--commit` (recarrega o cache sozinho, sem restart).
3. **OPÇÃO 1: a GERAÇÃO vai no `chip_type` para todo DDR/GDDR discreto** (H5TQ→`DDR3`, H5TC→`DDR3L`,
   H5AN/H5A→`DDR4`, H5C→`DDR5`, H5RS→`GDDR3`, HY5DU→`DDR1`, H5PS/HY5PS→`DDR2`), espelhada no `subtype`.
   ❌ NUNCA `chip_type="RAM"`/`"DDR"` genérico. Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ a geração** (1–3 palavras). ❌ `"DDR3 SDRAM"`, `"LPDDR4X standalone"`, `"Graphics"`, densidade, bus width, tensão. (O engine copia `fam.subtype` ao resultado; o label é protegido por `canonical_gen`, mas escreva limpo.)
5. **`interface=""` para LPDDR standalone e eMCP/uMCP.** Nunca a geração de RAM no `interface`. Para DDR/GDDR, `interface` = **bus width** (`x8`/`x16`/`x4`), lido de `pn[6]` — nunca a geração.
6. **`emcp_ram` = tipo ANTES da capacidade** (`"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`). `emcp_nand` = só GB.
7. **Nunca inverta `val_primary`/`val_secondary` nos decode maps** — siga o padrão das linhas existentes do mapa. Nunca escreva `"por die"` no secondary (o engine já anexa). `decode_density_type` e `decode_cap_map` são mutuamente exclusivos na mesma família.
8. **Não confie em distribuidor/IA sem verificar** (Jotrin/WinSource/Shenzhen/LLM confundem Gb/GB, invertem primary/secondary, alucinam). Cruzar com `product.skhynix.com` / Alldatasheet / Octopart.
9. **⚠️ Ouro = IDENTIDADE, não as specs derivadas — atestar SEMPRE em tier-1.** Num `confidence="confirmed"`,
   o verificado é a **identidade** (o PN/laser-marking é real). `capacity`/`subtype`/`dram_density`/geração
   são **derivados** (de decode map, distribuidor ou inferência por prefixo) e **podem estar errados mesmo
   num confirmed**. Dois modos de falha que isso evita:
   - **Geração por prefixo sem atestar** — foi o erro `MT52L=LPDDR4` na Micron (era LPDDR3). Aqui: **H9DA é
     LPDDR1**, não LPDDR3 apesar do "H9D"; **H5TQ=DDR3 1.5V vs H5TC=DDR3L 1.35V**. O prefixo define — confirme.
   - **Sufixo de dies interpretado como multiplicador** — na SK Hynix o decode é 100% por decode map curado,
     então o "bug de dies" da Micron é impossível; ainda assim confira a chave contra o datasheet, nunca extrapole por padrão numérico.

### 0.3 Hierarquia de fontes (imutável)

```
1. product.skhynix.com / Glochip LPDDR page (Tier 1) → busca por PN, specs oficiais
2. Datasheet SK Hynix (dl.skhynix.com) → timing, tensão, package, pinout
3. Alldatasheet / LCSC com rastreabilidade SK Hynix
4. Octopart com fonte rastreável
5. Distribuidor B2B (Preduo, OMO) — só apoio; nunca rebaixa um confirmed
6. iFixit/GSMArena — chip_type confirmado por inspeção física
7. IA externa — ÚLTIMO RECURSO; verificar SEMPRE
```
Nunca fonte primária: fóruns asiáticos, WinSource sem rastreio, catálogos genéricos, eBay, IA sem verificação.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única da convenção: `chips/chip_types.py` (código).** Contexto geral: CLAUDE.md.
> DRAM discreta: geração no `chip_type`, espelhada no `subtype`. Gerenciada (eMMC/UFS/eMCP/uMCP/NAND):
> `subtype` = geração LPDDR (eMCP/uMCP) · vazio (eMMC/UFS). Unidade: densidade do **die** em `Gb`; pacote em `GB`.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1–5 / GDDR3 | a geração (`DDR3`, `DDR5`, `GDDR3`…) | espelha | bus width (`x8`/`x16`/`x4`) | `dram_density` (Gb/die) |
| LPDDR1–5X standalone | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| eMMC | `"eMMC"` | `""` | `"eMMC 5.1"` | `capacity` (GB) |
| UFS | `"UFS"` | `""` | `"UFS 2.1"`/`"UFS 3.1"` | `capacity` (GB) |
| eMCP / uMCP | `"eMCP"`/`"uMCP"` | geração RAM (`"LPDDR3"`/`"LPDDR5"`) | `""` | `emcp_nand` (GB) + `emcp_ram` (tipo+GB) |

**Regras absolutas:** `subtype` = só a geração (nunca `"4Gb"`, `"x8"`, `"1.35V"`, `"standalone"`, `"SDRAM"`,
`"Mobile"`, `"PC"`, `"Graphics"`). `dram_density` = Gb por die (DDR/GDDR). `capacity` = pacote em bytes (nunca Gbit).
`emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip` = tudo o resto (tensão, velocidade, organização, avisos).

**Label da caixa:** DDR `{subtype}+{dram_density Gb}G` (`DDR3+2G`) · LPDDR `{chip_type}+{cap GB}G`
(`LPDDR4X+4G`) · eMCP `EMCP{nand}+{ram}` · eMMC `EMMC{cap}GB` · UFS `UFS{cap}GB`.

---

## 2. Anatomia do PN — como LER um chip SK Hynix

> As posições e os mapas que cada uma referencia. **Os valores das chaves vivem nos decode maps do
> yaml** (`maps:` em `hynix.yaml`) — aqui fica a ESTRUTURA (durável) e as pegadinhas.

**DDR PC (H5TQ/H5TC, H5AN, H5A, H5C, H5PS, HY5PS, HY5DU):** o bloco de capacidade fica logo após o
prefixo (`pn[4:6]` na maioria; `pn[3:5]` em H5A/H5C; `pn[5:7]` nos prefixos `HY5…` de 5 chars) → mapa
`HYX_DDR{n}_*_CAP`. Depois vêm **organização/bus width** (`pn[6]`: `4`=x4 · `6`=x16 · `8`=x8) e **geração de
revisão** (`pn[7]`). Sufixo = velocidade (não é capacidade).
- ⚠ **H5TQ = DDR3 1.5V; H5TC = DDR3L 1.35V** — decode idêntico, o sufixo (`C` vs `A`) e o prefixo distinguem.
- ⚠ **H5AN antes de H5A** (prefixo mais longo vence): `H5AN…` nunca cai em H5A.
- ⚠ **H5TC…MR = DDP** (dois dies): `dram_density` por die, `capacity` por die; o pacote soma no módulo.

**LPDDR standalone (H9CC/H9CK, H9HC/H9HK/H9HCN, H54G, H9JK, H58G, H9TK, H5MS/HY5MS):** capacidade em
**1 char** (`pn[7]` nas famílias `H9…NNN…`; `pn[4]` em H54G/H58G) → mapa `HYX_LPDDR*_CAP`. `interface=""` sempre.
- ⚠ **H9CC = x32, H9CK = x64** (dual-channel) — compartilham `HYX_LPDDR3_CAP`.
- ⚠ **H9HCN** (5 chars, priority menor): `pn[4]='N'` = RAM pura; o `'C'` em `pn[3]` atesta LPDDR4X (0.6V), **não é capacidade**.
- ⚠ **H54G/H58G têm DOIS sistemas de código** (numérico E alfabético) no mesmo prefixo — não é erro; `pn[5]` = organização de banco, **nunca capacidade**.
- ⚠ **HY5MS ≠ H5MS** — esquemas de decode diferentes, **jamais compartilhar mapas**.

**eMMC/UFS (H26M/H26T, H28U/H28S, HN8T/HN8G):** capacidade em `pn[4]` (1 char) ou `pn[4:6]` (HN8) → `HYX_EMMC_CAP`/`HYX_H28*_CAP`/`HYX_HN8_CAP`.
- ⚠ **`H26M64…` = 32GB** (não 64GB): `pn[4]='6'`=32GB é o código de capacidade; o `'4'` seguinte é organização.
- ⚠ **UFS e eMMC = BGA-153 idêntico**, eletricamente **incompatíveis** — triagem obrigatória pelo PN antes do socket.

**eMCP/uMCP (H9TQ, H9TP, H9DP, H9DA, H9HP, H9HQ, H9HR, H9RT):** NAND em `pn[4:6]`, RAM em `pn[6:8]` (mapas
`HYX_*_NAND_CAP` + `HYX_*_RAM_CAP`, onde `val_primary` da RAM já é a string `"LPDDR{n} {cap}"`).
- ⚠ **COLISÃO `"16"`:** em H9TQ (`HYX_EMCP_NAND_CAP`) `16`=**16GB**; em H9HP (`HYX_H9HP_NAND_CAP`) `16`=**128GB**. Mapas separados obrigatórios — nunca unir.
- ⚠ **H9DA = eMCP LPDDR1 legado** (~2012-2015), decode **diferente de todos**: NAND em 1 char (`pn[4]`), RAM em `pn[7:9]`, `pn[5:7]='GH'` é filler. RAM é **LPDDR1** (não LPDDR3). Notação Preduo "X+Y": Y em **Gb** (`"2G"`=2Gbit=**256MB**, não 2GB).
- ⚠ **Prefixo define a geração de RAM:** H9DA=LPDDR1, H9TP/H9DP=LPDDR2, H9TQ=LPDDR3, H9HP/H9HQ=LPDDR4X, H9HR/H9RT=LPDDR5.
- ⚠ **H9DP** RAM em 1 char (`pn[7]`); `pn[6]='A'` = controlador fixo, invisível. **H9RT** usa NAND `"dígito+G"` (`0G/1G/2G`).

**GDDR3 (H5RS):** só routing (sem decode de capacidade) — aciona alerta no operador.

---

## 3. Armadilhas e Decisões Arquiteturais

- **Colisão `"16"` H9TQ (16GB) × H9HP (128GB)** — mapas separados; humano editando o mapa errado gera valor catastrófico. Nunca unir. (§2)
- **H5TQ8G43 não existe** — SK Hynix nunca fez DDR3 1.5V 8Gbit x4. Se aparecer → suspeito de remarked (de H5TC8G43AMR DDP).
- **H5TC8G43AMR = DDP, 1GB total** (2 dies de 4Gbit): `dram_density="4Gb"` por die, `capacity="512MB"` por die.
- **H9HCNNNECMML (6GB) — divergência de família:** 6GB (48Gbit) pode pertencer a **H9HKNNN** (376/556-ball), não H9HCNNN (200-ball). No banco com flag de divergência. Confirmar contando balls no chip físico.
- **H28M — prefixo sem documentação** (só H28U/H28S são UFS documentados). Decode desativado (`decode_cap_pos: null`) para não exibir valor especulativo. Hipótese: misprint de H26M.
- **HKMAG — ⚠ prefixo não documentado nos catálogos SK Hynix** (os UFS reais são H28U/H28S/HN8T/HN8G). Está no yaml como UFS 2.1 magra — **confirmar se é real ou dado sujo** antes de expandir.
- **Interface de LPDDR = erro histórico:** antes de 2026-06, 11 famílias tinham a geração no `interface` (`interface="LPDDR3"`). Corrigido. `interface="LPDDR*"` em qualquer marca = bug.
- **UFS × eMMC = BGA-153 idêntico, incompatíveis** — triagem pelo PN antes do socket (risco de destruir o chip).
- **"por die" duplicado:** nunca no `val_secondary` do mapa — o engine já anexa.

---

## 4. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no **`ProfitabilityConfig`**
(admin, você edita). ⚠ **É dado mutável** — os limiares E quais gerações são rentáveis **mudam com o
mercado** — por isso este doc **NÃO cita valores nem veredictos por família** (datariam no dia seguinte).

Regras duráveis (essas não mudam): nunca reimplementar/hardcodar a regra (só `assess_profitability`);
`capacity` sempre em MB/GB, nunca Gbit (senão → **INDETERMINADO** = bloqueador de produção);
`is_dead_by_generation` manda geração morta ao descarte mesmo sem banco (a lista de gerações vive no
código/config). Como o engine lê a capacidade: `dram_density` (DDR/GDDR) → Gb direto; senão `capacity`
→ GB; eMCP/uMCP → `emcp_nand`/`emcp_ram`.

---

## 5. Gaps e Roadmap (o durável — o resto está no yaml)

- **H5C DDR5 `G6`=8GB (64Gbit)** — previsto no JEDEC, sem PN físico rastreado. Adicionar quando aparecer confirmado.
- **H58G LPDDR5 24GB (192Gbit)** — chave desconhecida; chip existe em devices, sem PN avulso rastreado.
- **H9HCNNNECMML (6GB)** — confirmar se é H9HCNNN (200-ball) ou H9HKNNN (376/556-ball) contando balls.
- **H5RS GDDR3** — só routing; criar decode se chegar em volume.
- **H28M / HKMAG** — prefixos sem documentação oficial; investigar antes de expandir.
- **NÃO adicionar** chave de capacidade por padrão numérico — só com PN âncora + fonte Tier 1-2.

---

## 6. Fontes de pesquisa

Tier 1: `product.skhynix.com`, Glochip LPDDR, Alldatasheet, LCSC, iFixit (chip físico). Tier 2: Octopart,
Preduo. Tier 3: OMO, brokers. **Evitar p/ capacidade:** HardDiskDirect ("(8GB)" para 8Gbit), Jotrin/WinSource
(invertem Gb/GB). Sempre conferir: `Xbit ÷ 8 = YB`.

---

## 7. Histórico (o *porquê* — durável)

- **2026-06:** 11 famílias LPDDR/eMCP/uMCP tinham a geração no `interface` → corrigido para `""`.
- **2026-06-25:** `HYX_LPDDR3_CAP` ganhou `E`=6GB (48Gbit) e `F`=8GB (64Gbit) — comentário "BLOQUEADO" anterior estava errado; Preduo tier-1 confirmou multi-die.
- **2026-06-27 (Micron):** lição transferida (regra #9) — `MT52L=LPDDR4` era LPDDR3; o tier-1 pegou antes do bulk corromper. Geração por prefixo sem atestar é o modo de falha nº1.
- **2026-06-29:** subtypes já canônicos no código + `canonical_gen` protege o label (não é mais "bug pendente").

> O inventário de chaves/mapas vive no **`hynix.yaml`** (gramática); os **known_parts** confirmados
> (com a proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2), submetidos via `submit_known_parts`.
> Tudo que é cross-marca (comandos, convenção, rentabilidade, arquitetura) está no **CLAUDE.md** — o
> único `.md` mantido, e é quem aponta pro contrato de autoria do yaml.

---

> **Regra de trabalho:** Claude edita a `hynix.yaml`. O usuário roda `load_brands` (sempre `--brand hynix`
> dry-run antes do `--commit`). **Ponto mais importante:** o decode é 100% por decode map curado — atestar a
> IDENTIDADE em tier-1 e nunca extrapolar chave por padrão numérico (regra #9).
