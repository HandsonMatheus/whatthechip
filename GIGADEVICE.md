> ⚠️ **O CONHECIMENTO É YAML** (desde jul/2026). As famílias, decode maps e PNs confirmados da
> GigaDevice vivem em **`chips/knowledge/gigadevice.yaml`**, carregado por `load_brands`. Para
> **adicionar ou corrigir um chip, edite o yaml** seguindo o contrato de autoria (via `CLAUDE.md`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do yaml (decode key→valor, inventário de
> famílias, known_parts) nem valores mutáveis (rentabilidade). Aqui: **anatomia do PN, armadilhas,
> convenção, fontes**. **`CLAUDE.md`** é o único `.md` cross-marca mantido (convenção, comandos §5,
> arquitetura + aponta pro contrato de autoria).

---

# GIGADEVICE.md — Referência Técnica GigaDevice

**GigaDevice Semiconductor** (兆易创新, Zhaoyi Innovation) — fabricante chinês, fundado 2005. Code WTC:
`GGD`. Na esteira: **NOR Flash SPI** (`GD25…` — BIOS/firmware, alta frequência), **NAND Flash SPI**
(`GD5F` — equipamentos de rede), **DDR4 SDRAM** (`GDQ` — nicho). A lista viva de famílias/mapas/known_parts
está na **`gigadevice.yaml`**.

---

## 1. Convenção (OPÇÃO 1 — regras estáveis)

Fonte única: `chips/chip_types.py`. **DRAM discreta:** geração no `chip_type`, espelhada no `subtype`.
**NOR/NAND:** `chip_type="NOR Flash"`/`"NAND Flash"`, `subtype` = célula/`"SPI NOR"`/`"SPI NAND"`,
`interface="SPI"`. `capacity` em bytes (Mbit ÷ 8). Detalhes gerais: CLAUDE.md.

---

## 2. Anatomia do PN — como LER um chip GigaDevice

**NOR Flash (`GD25[L][tipo][cap][rev]-[pkg]`):**
- `GD25` = NOR SPI 3.3V; `GD25L` = 1.8V.
- Letra após `25`/`25L` = **interface/variante**: `Q`=Quad SPI (comum) · `B`=Enhanced Quad (4I/O) · `D`=Dual · `F`=ECC · `R`=RPMC · `T`=DTR · `E`=WLCSP compacto.
- ⚠ **Código de capacidade NÃO-linear e de comprimento variável** — **`"40"` = 4Mbit (0,5MB), NÃO 40Mbit**. Decode posicional **inviável**; capacidade vem de datasheet / `known_parts`. Ex.: `GD25Q128ESIG` → `128`=128Mbit=16MB.

**NAND Flash (`GD5F[densidade][série]…`):**
- `pn[4]` (1 char) = **densidade** → mapa `GD5F_NAND_CAP` no yaml. Série `pn[5:7]`: `GQ4` (Gen1) · `GQ5` (Gen2) · `GM9` (Gen3, ECC embutido).

**DDR4 SDRAM (`GDQ[dens][pkg][org][V][rev]-[temp][speed]`):**
- `pn[3]` = densidade (`2`=4Gbit/512MB, único confirmado); `pn[4]` = package (`B`=FBGA-96); `pn[5]` = org (`F`=×16); `pn[6]` = tensão. Sufixo = temp (C/W) + speed (E/Q/J = 2400/2666/3200). Fonte: datasheet DS-00808-GDQ2BFAA-Rev1.4. Os PNs confirmados vivem nos `known_parts`.

---

## 3. Armadilhas específicas (o durável)

- ⚠ **`"40"` ≠ 40Mbit (é 4Mbit)** — os códigos de capacidade GD25 são **não-lineares e de comprimento variável**; nunca decode posicional, sempre datasheet / known_part.
- ⚠ **GD5F ≠ GD25** — tipos de chip completamente distintos (NAND SPI vs NOR SPI). Não confundir pelo "GD".
- ⚠ **GD5F é SPI-like, NÃO ONFI/Toggle** — protocolo NOR sobre NAND. Não classificar como NAND paralela.
- ⚠ **GDQ: `B` (pn[4], FBGA-96) confundido com `6` no laser** — se o operador reportar `GDQ26FAA`, é provável `GDQ2BFAA` mal lido; pedir conferência visual no datasheet antes de dar como desconhecido.

---

## 4. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` (código) + `ProfitabilityConfig` (admin, market-variable). Padrão
durável: NOR Flash de baixa densidade (firmware commodity) = baixo valor; DDR4 (GDQ) = rentável. `capacity`
em MB/GB (nunca Gbit) senão → INDETERMINADO. Sem números aqui.

---

## 5. Fontes Tier 1

Datasheet GigaDevice (gigadevice.com — DS-00808 para o GDQ), DigiKey (buscar `GD5F`), LCSC (ex.: C2937367 =
GDQ2BFAA-CE). ⚠ Não usar distribuidor B2C / IA sem datasheet — confundem Gb/GB, capacidade e interface.

> Inventário de famílias/chaves e provenância por-PN: **`gigadevice.yaml`**. Comandos, convenção completa,
> rentabilidade, contrato de autoria: **CLAUDE.md**.
