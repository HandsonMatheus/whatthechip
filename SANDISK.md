> ⚠️ **O CONHECIMENTO É YAML** (desde jul/2026). As famílias e PNs confirmados da SanDisk vivem em
> **`chips/knowledge/sandisk.yaml`**, carregado por `load_brands`. Para **adicionar ou corrigir um
> chip, edite o yaml** seguindo o contrato de autoria (via `CLAUDE.md`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do yaml (inventário de famílias, known_parts,
> formato de campos) nem valores mutáveis (rentabilidade). Aqui: **anatomia do PN, armadilhas, a história
> SanDisk×WD, convenção, fontes**. **`CLAUDE.md`** é o único `.md` cross-marca mantido (convenção,
> comandos §5, arquitetura + aponta pro contrato de autoria).

---

# SANDISK.md — Bíblia Técnica e de Negócio

**SanDisk** (code WTC `SDK`) — armazenamento embarcado (eMMC, eMCP, UFS) pra smartphone/tablet. Na
bancada eMiner aparece com frequência moderada, predominando **eMMC standalone** (gerações 4.41–5.1).
A lista viva de famílias/known_parts está na **`sandisk.yaml`** (11 famílias, **sem DecodeMaps**).

> **É uma marca só — ver §5.1 (SanDisk × Western Digital).** O PN gravado no chip sempre foi `SD…`;
> só a documentação levou marca WD por um período (2016–2025).

---

## 1. Convenção (OPÇÃO 1 — regras estáveis)

Fonte única: `chips/chip_types.py`. Para os tipos gerenciados da SanDisk:

- **eMMC:** `chip_type="eMMC"`, `subtype=""`, `interface`=versão (`"eMMC 5.1"`), `capacity` em GB.
- **UFS:** `chip_type="UFS"`, `subtype=""`, `interface`=versão (`"UFS 2.1"`), `capacity` em GB.
- **eMCP:** `chip_type="eMCP"`, `subtype`=geração RAM (`"LPDDR3"`/`"LPDDR4"`), `interface=""` (sempre vazio), capacidade via `emcp_nand` (só GB) + `emcp_ram` (**tipo ANTES da capacidade**: `"LPDDR3 2GB"`, nunca `"2GB LPDDR3"`).

`subtype` = **só** a geração da RAM (eMCP) ou vazio (eMMC/UFS) — nunca "iNAND", "standalone", velocidade,
tensão. O label é protegido por `canonical_gen` (fail-open). Detalhes gerais: CLAUDE.md.

---

## 2. Anatomia do PN — SanDisk é DECLARATIVO (a chave da marca)

**Diferença fundamental vs Samsung/Hynix/Micron:** a capacidade **não** está numa posição fixa — está
sempre no **sufixo após o traço** (declaração de fábrica):

```
[Prefixo Família] [Die Code / variante] - [Capacidade]
                                            -8G=8GB · -16G · -32G · -64G · -128G  (G = Gigabyte, não Gigabit)
```

⚠ **Decode posicional é IMPOSSÍVEL** — o die code intermediário tem **comprimento variável**
(`SD7DP24C-4G`=10 chars, `SD7DP24C-16G`=11, `SD7DP25F-128G`=12), então não há posição fixa pra
capacidade. Por isso **todas** as famílias SanDisk têm `decode_cap_pos: null` e **`sandisk.yaml` não tem
DecodeMaps**. Consequência crítica:

> **Chip SanDisk sem `known_part` no banco → `profitable="INDETERMINADO"`.** O engine classifica a
> família (tipo + interface) mas **não tem como extrair a capacidade** pela gramática. `known_parts` é a
> **única** fonte de capacidade da marca. A missão contínua é confirmar PNs à medida que aparecem.

**Normalização:** o engine faz `re.sub(r"[^A-Z0-9]", "", pn)` → o traço some (`SDIN9DW4-16G` →
`SDIN9DW416G`). Grave o PN normalizado nos `known_parts` (o loader aceita com traço, mas o padrão é sem).

**Famílias (orientação — inventário completo na `sandisk.yaml`):** eMMC = `SD5DH`/`SD7DP`/`SDINB`/`SDMAG` +
`SDIN` (fallback genérico, priority 80); UFS = `SDINDDH`/`SDINEDK`/`SDINFD`/`SDHQB`; eMCP = `SDAD`/`SDEM`.
O engine casa o prefixo mais específico primeiro (`SDINB` eMMC vence `SDIN` genérico; UFS vence ambos).

---

## 3. Armadilhas específicas (o durável)

- ⚠ **`SDINB` é eMMC, NÃO UFS** (reclassificado jun/2026). Começa com `SDIN` mas é eMMC 5.1 — sub-linhas SDINBDG4 (iNAND 7250) / SDINBDD4 (7350) / SDINBDA4 (7550), confirmadas nos product briefs oficiais. As **UFS reais** são `SDINDDH`/`SDINEDK`/`SDINFD`. `SDINB` (priority 40) vence `SDIN` (80).
- ⚠ **UFS e eMMC compartilham BGA 153-ball visualmente idêntico** mas são **eletricamente incompatíveis**. Triar SEMPRE pelo prefixo do PN antes de encostar no socket.
- ⚠ **eMCP `SDAD`: a geração da RAM NÃO está no PN** — vem do **ball count físico**: **221-ball = LPDDR3, 254-ball = LPDDR4** (regra de ouro; ex.: `SDADA4DR-64G`=254-ball LPDDR4). Nunca assumir geração RAM sem ball count ou fonte Tier 1.
- ⚠ **"16+2" vs "16+16":** Preduo escreve `"16+16"` = 16GB NAND + 16**Gbit** LPDDR3; mercado BR/PY usa `"16+2"` = ambos em GB (16Gbit ÷ 8 = 2GB). No banco: `emcp_nand="16GB"`, `emcp_ram="LPDDR3 2GB"`.
- O sufixo `-16G` de um eMCP refere-se ao **NAND** (não à soma).

---

## 4. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` + `ProfitabilityConfig` (admin, market-variable). SanDisk usa as
mesmas regras de eMMC/eMCP/UFS das outras marcas — **sem parâmetro SanDisk-específico**. Padrão durável:
UFS e eMMC/eMCP de boa capacidade = rentável; **sem capacidade no banco → INDETERMINADO** (bloqueador de
triagem, resolvido só confirmando o PN). Sem números aqui.

---

## 5. Contexto de negócio

### 5.1 SanDisk × Western Digital — o "mix" foi só na doc, nunca no PN

Linha do tempo: SanDisk foi **comprada pela Western Digital em 2016** e **voltou a ser independente em
21/fev/2025** (spin-off; Nasdaq: SNDK), ficando com todo o negócio de flash/NAND. A WD hoje é **só HDD**
(fora do domínio do WTC). Regras imutáveis pro operador:

- O **PN gravado no chip sempre teve prefixo `SD`** (`SDIN…`, `SD7DP…`, `SDAD…`). A WD **nunca** criou chip de memória com prefixo "WD". O código que o operador lê é sempre SanDisk.
- O logo "WD" aparece nos produtos de **consumo** (SSD/HDD), **não** no die de memória embarcada.
- Só a **documentação** (datasheets, product briefs) de 2016–2025 saiu com marca WD (westerndigital.com). Um PDF "Western Digital" pra um PN `SD…` é o **mesmo produto** — não outra marca. Pós-split a doc volta a sandisk.com (westerndigital.com ainda hospeda os legados).

**No WTC: uma marca só, `SanDisk` (SDK).** Não existe marca "Western Digital" de chip de memória pra catalogar.

---

## 6. Fontes de pesquisa

Hierarquia (Tier-1→baixo): **sandisk.com / westerndigital.com** (product briefs, datasheets — mesmo
produto, ver §5.1) → datasheet SanDisk histórico (ex.: doc# 80-36-03462, iNAND eMMC 4.41) →
Octopart/Mouser/Avnet (distribuidor autorizado) → distribuidor B2B rastreável (só apoio, nunca rebaixa
`confirmed`) → **Preduo** (confiável pra tipo/ball count, **não** pra specs elétricos) → IA (último recurso,
sempre verificar). **Nunca fonte única:** yoycart/chinahao sem cruzamento, eBay, catálogo Shenzhen sem rastreio.

> Inventário de famílias e provenância por-PN (nas `notes`): **`sandisk.yaml`**. Comandos, convenção
> completa, rentabilidade, contrato de autoria: **CLAUDE.md**.
