# Micron `getpartcatalog` — índice de catálogos (Fase 0, sonda 2)

> Working file da Fase 2 identity-only (temporário, apaga com o plano). Fonte: endpoint XHR
> capturado no §1.4 do `PLANO_MICRON_IDENTITY_ONLY_FASE2.md`, **re-validado headless/sem-login
> em 2026-07-15** (uMCP 14 partes, eMCP 15 partes, ambos HTTP 200 JSON).

## Template de URL (CONFIRMADO)

```
https://www.micron.com/content/micron/us/en/products/<PATH>/part-catalog/
  _jcr_content.products.json/getpartcatalog/<2-últimas-pastas-de-PATH>/-/en_US.json
```

`<PATH>` = caminho do produto; as `<2-últimas-pastas>` repetem as duas últimas do PATH. Responde
`application/json` sem login, headless. Re-executável → **fonte incremental permanente**.

**⚠ RAÍZES AEM CONFIRMADAS (2026-07-16)** — a lista de PATHs abaixo (⟳) foi corrigida; a fonte da
verdade é a `CATALOGS` do `scripts/micron_catalog_snapshot.py`. As raízes por família **diferem**:
- **MCP:** `multichip-packages/<slug>` (ex.: `multichip-packages/ufs-based-mcp`) — validado.
- **Discreta:** `memory/lpddr-components/<slug>` e `memory/dram-components/<slug>` — ⚠ DDR tem sufixo
  `-sdram` (`ddr4-sdram`, não `ddr4`); LPDDR4 = catálogo `LPDDR4/4X` (4X junto).
- **eMMC/UFS standalone:** `storage/managed-nand/<slug>` (raiz `storage/`, não `memory/`).
- **Obsoletos:** `obsolete/obsolete-<slug>` (ex.: `obsolete/obsolete-ddr4-sdram`).
- (o antigo chute `lpddr-components/…` / `dram-components/…` sem a raiz deu **404** — corrigido.)

## Forma da resposta (campos que importam)

`details[]` por parte:
- `part-number` — COMPLETO, com sufixo/velocidade (ex.: `MT29VZZZBD81SLSL-046 W.22D`). ⚠ normalizar
  (tirar espaço, hífen, sufixo pós-espaço) antes de casar com o `part_number` do banco.
- `part-key` — slug normalizado (ex.: `mt29vzzzbd81slsl-046-w.22d`).
- `part-name` — string oficial curta (ex.: `UMCP 560G VFBGA`, `EMCP 1088G TFBGA`). Traz o TOTAL.
- `attr[]` (por `name`):
  - **`Technology`** → tipo + célula NAND + geração RAM numa coluna (ex.: `uMCP TLC LPDDR4`,
    `uMCP TLC LPDDR5`, `eMCP TLC LPDDR4`, `NAND MCP SLC LPDDR4`). **Fonte oficial de TIPO.**
  - **`Protocol`** → interface (`UFS2.2`/`UFS3.1`/`MMC5.1`). Fonte de `interface`.
  - **`Component Density`** → TOTAL do pacote em Gbit (ex.: `560Gb`). ⚠ MCP: é NAND+RAM somado —
    **nunca vira `capacity`**; vai só em `notes`. Discreto: é a densidade do dispositivo.
  - `Component Config` (às vezes) → ex.: `130Gb x32`.
  - `Part Status Code` → Production/End of Life/Obsolete/Contact Sales.

### Mapeamento attr → campo (por segmento)
- **Gerenciados (A):** `Technology`→`chip_type`(uMCP/eMCP) + `subtype`(geração LPDDR) · `Protocol`→
  `interface` · `Component Density`→**`notes`** (TOTAL, com a conta Gb÷8). SPLIT nunca sai daqui.
- **Discreta (B):** `Technology`→`chip_type`/`subtype` (corrige LPDDR4X→LPDDR5X) · `Component
  Density`→`capacity`(LPDDR, ÷8) **ou** `density_gbit`(DDR).

## Paginação
Catálogos gerenciados testados vieram COMPLETOS e pequenos (14/15), sem campo de página. **Aberto**
p/ catálogos grandes (DDR/LPDDR): o snapshotter deve imprimir `len(details)` por catálogo p/ o dono
cruzar com o "Show all" da UI (a UI tem paginação; confirmar se o JSON traz tudo de uma vez).

## Lista de catálogos

Legenda: ✓ = URL validada nesta sessão · ⟳ = PATH inferido do §1.4/docstring, **confirmar slug**
antes de snapshotar (o snapshotter trata 404 e resolve pelo índice `micron.com/products/obsolete`).

### Gerenciados — Segmento A (eMCP/uMCP/eMMC/NAND-MCP)
| PATH | Segmento | Status |
|---|---|---|
| `multichip-packages/ufs-based-mcp` | uMCP | ✓ (14) |
| `multichip-packages/emmc-based-mcp` | eMCP + NAND-MCP | ✓ (15) |
| `multichip-packages/nand-based-mcp` | NAND-MCP | ⟳ |
| `multichip-packages/obsolete-umcp-catalog` | uMCP obsoleto | ⟳ |
| `multichip-packages/obsolete-nand-mcp-catalog` | NAND-MCP obsoleto | ⟳ |
| eMMC standalone (`.../emmc`) + `obsolete-emmc` (MTFC+N2M) | eMMC | ⟳ |
| UFS standalone (`.../ufs`) + `obsolete-universal-flash-storage` | UFS | ⟳ |

### Discreta — Segmento B (LPDDR / DDR)
| PATH | Segmento | Status |
|---|---|---|
| `lpddr-components/lpddr3` · `/lpddr4` · `/lpddr4x` · `/lpddr5` · `/lpddr5x` | LPDDR | ⟳ |
| `dram-components/ddr4` · `/ddr5` | DDR | ⟳ |
| `obsolete-lpddr` · `obsolete-lpddr4` · `obsolete-lpddr5` · `obsolete-lpddr5x` | LPDDR obsoleto | ⟳ |
| `obsolete-ddr4-sdram` · `obsolete-ddr3-sdram` · `obsolete-ddr2-sdram` · `obsolete-sdram` | DDR obsoleto | ⟳ |
| `obsolete-rldram-memory` · `obsolete-gddr6` | especial | ⟳ |

⚠ **Pegadinha real do índice (§1.4):** links rotulados "LPDDR3"/"LPDDR2" apontam p/ slugs
`obsolete-lpddr5`/`obsolete-lpddr4`. **Validar cada catálogo pelo CONTEÚDO (`Technology`), nunca
pelo rótulo/slug.**

### NAND raw / NOR — Segmento C (quase tudo dead-by-gen → só tipo)
`obsolete-mlc-nand` · `obsolete-tlc-nand` · `obsolete-slc-nand` · `obsolete-3d-nand` ·
`obsolete-parallel-nor` · `obsolete-serial-nor` · `obsolete-xccela-flash` — todos ⟳.

## Achados da sonda de conteúdo (2026-07-16) — reformam a Fase C/E

1. **Tipo discreto vem do PREFIXO do PN, NÃO da coluna `Technology`.** O `lpddr4` (133)
   mistura `MT53B/D`=LPDDR4, `MT53E`=LPDDR4X e `MT40A`=DDR4, TODOS com Technology genérico
   "LPDDR4"/"DDR4". Regra fina (MICRON.md §2): `MT53E`→LPDDR4X, `MT53B/D`→LPDDR4,
   `MT62F`→LPDDR5X. ⚠ Fase C: distinguir 4X/5X pelo **prefixo**; o catálogo entra como
   prova de existência + fonte de `Component Density`.
2. **O formato abreviado `-DC` ESTÁ no catálogo** (contra o §1.4a do plano): `lpddr5` tem
   `MT62F1DCD4CZ-DC`, `MT62F2BAD2DS-DC` ao lado do padrão. A cobertura dos automotivos
   abreviados é melhor que o temido — a matriz de cobertura (pós-export) quantifica.
3. **MT29C legado está no `obsolete-nand-mcp-catalog`** (88): prefixos `MT29C1/2/4/8` +
   `MT29GZ/RZ/UZ/AZ`, incl. `MT29C8G96MAZBADJV-5 IT` (irmão do caso JW500). Fonte da
   recategorização eMCP→MCP (Fase C.2).
4. **`MT62F` cai em `lpddr5` E `lpddr5x`, ambos Technology "LPDDR5".** A distinção 5 vs 5X
   dentro do MT62F precisa de sinal fino (tensão/velocidade/attr) — investigar na Fase C
   ANTES de gravar 5X em massa (não assumir pelo slug do catálogo).
5. Slugs corrigidos: uMCP obsoleto = `obsolete/obsolete-universal-flash-storage`;
   UFS standalone = `storage/managed-nand/universal-flash-storage`; LPDDR3 corrente não
   existe (só `obsolete-lpddr`).

## Limites já medidos (honestidade)
- O **abreviado automotivo** (`MT62F1BAD4BS-DC…`) **não aparece** no catálogo LPDDR5X (§1.4a) →
  os 567 discretos abreviados caem no DigiKey/datasheet, não aqui.
- O **cluster do estoque** `MT29VZZZ7D7…` / `MT29TZZZ7D7…` (JZ083/JZ013) **não está** nem no
  ufs-based-mcp nem no emmc-based-mcp (confirmado hoje) → precisa DigiKey/datasheet.
- Micron novos (`MT29GZ…` NAND-MCP SLC) aparecem no emmc-based-mcp com `Technology="NAND MCP SLC
  LPDDR4"` — atenção: "NAND MCP" ≠ "eMCP" na coluna oficial.
