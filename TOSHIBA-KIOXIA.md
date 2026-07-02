> ⚠️ **O CONHECIMENTO É YAML** (desde jul/2026). As famílias, decode maps e PNs confirmados vivem em
> **`chips/knowledge/toshiba-kioxia.yaml`**, carregado por `load_brands`. Para **adicionar ou corrigir
> um chip, edite o yaml** seguindo o contrato de autoria (via `CLAUDE.md`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados do yaml (decode key→valor, inventário de
> famílias, known_parts, formato de campos) nem valores mutáveis (rentabilidade). Aqui: **a consolidação
> 1-marca, anatomia do PN, armadilhas, fontes**. **`CLAUDE.md`** é o único `.md` cross-marca mantido
> (convenção, comandos §5, arquitetura + aponta pro contrato de autoria).

---

# TOSHIBA-KIOXIA.md — Bíblia Técnica e de Negócio

**Toshiba-Kioxia** (code WTC `TXK`) — 3º maior fabricante mundial de NAND Flash. Na bancada eMiner
aparece quase só como **eMMC standalone (THGBM)** em Android de entrada/mid-range; volume menor que
Samsung/Hynix, boa liquidez B2B nas densidades maiores. A lista viva de famílias/mapas/known_parts está
na **`toshiba-kioxia.yaml`** (11 famílias + mapas THGBM_CAP/GEN).

## ⚠ É UMA MARCA SÓ (consolidação 2026-07-01)

Toshiba e Kioxia são a **MESMA empresa** — a divisão de memória da Toshiba foi **renomeada KIOXIA em
out/2019** (mesmas fábricas, mesmo esquema de PN). O WTC tinha 3 brands (Toshiba / Kioxia / KIOXIA-dup),
gerando ambiguidade de prefixo → foram **fundidos numa marca única `Toshiba-Kioxia`** (consolidação
concluída em jul/2026).

- Chips **pré-2019** têm silkscreen **"TOSHIBA"**; **pós-2019**, **"KIOXIA"** — mesmo fabricante, **mesmo PN** (THGBM coexiste nas duas eras).
- No banco, `brand_name="Toshiba-Kioxia"` pra **todos** (THGBM/TYC/TYD/TH58 antigos E THGAM/THGJF/THGAF novos). **Não** há mais distinção de brand por prefixo, nem criar família duplicada por era.

---

## 1. Convenção (OPÇÃO 1 — regras estáveis)

Fonte única: `chips/chip_types.py`. Para os tipos da Toshiba-Kioxia:

- **eMMC (THGBM, THGAM…):** `chip_type="eMMC"`, `interface`=versão (`"eMMC 5.0"`/`"5.1"`). Pro THGBM o engine decodifica a versão via mapa THGBM_GEN; em known_part escreva explícito. Nunca `"Flash"`/`"NAND"`/`"TLC"` no `chip_type`.
- **UFS (THGJF/THGAF):** `chip_type="UFS"`, `interface`=versão (`"UFS 2.1"`/`"3.1"`/`"4.0"`/`"4.1"`), `capacity` em GB/TB.
- **eMCP (TYC/TYD):** `chip_type="eMCP"`, `subtype`=geração RAM (`"LPDDR2"`/`"LPDDR3"`), `interface=""`, capacidade via `emcp_nand` (tipo+cap: `"eMMC 4.5 4GB"`) + `emcp_ram` (**tipo ANTES**: `"LPDDR2 512MB"`).
- **SDRAM (TY890A):** `chip_type="SDRAM"`. Detalhes gerais: CLAUDE.md.

---

## 2. Anatomia do PN — THGBM (a família de decode completo)

```
pn[0:5]  = "THGBM"   prefixo fixo
pn[5]    = geração/versão eMMC → mapa THGBM_GEN (N/T/F/B = 5.0 · H/J/U = 5.1)
pn[6]    = processo (normalmente 'G'; sem decode)
pn[7:10] = chave de capacidade (3 chars) → mapa THGBM_CAP
           pn[7]=densidade/die · pn[8]=tipo de stack · pn[9]=nº de dies
pn[10]   = tier de qualidade (sem decode)
pn[11:13]= "BA" (package BGA153)
pn[13]   = grau: I=consumer · U=industrial
pn[14]   = variante de bin/temperatura (sem decode)
```
**Comprimento canônico: 15 chars.** As chaves de decode (THGBM_CAP/GEN) e seus valores vivem no yaml.

> **Regra de densidade (durável):** `pn[7]` é a densidade **por die em Gbit** (`Gbit ÷ 8 = GB`), e
> `pn[9]` multiplica pelo **nº de dies**. Ex.: `pn[7]='8'`=64Gbit/die=8GB × `pn[9]='4'` dies = **32GB
> total**. Confira essa matemática antes de propor uma chave nova — e **nunca** adicione chave por
> "padrão matemático" sem um PN âncora + fonte Tier-2 (§THGBM_CAP tem chaves bloqueadas de propósito).

**Demais famílias (orientação — inventário e specs na `toshiba-kioxia.yaml`):** magras (cobertura só por
known_parts, sem decode posicional) = `THGAM` (eMMC 5.1 BiCS, Kioxia pós-2019), `THGJF` (UFS 3.1/4.0/4.1),
`THGAF` (UFS 2.1), `TYC` (eMCP LPDDR2, BGA-162), `TYD` (eMCP LPDDR3, BGA-221), `THGJFBT` (eMMC), `TH58`
(NAND raw). `TY890A` = SDRAM (só known_parts).

**Desativadas (`active:false`, jun–jul/2026):** `THGBMFG`/`THGBMHG` (interceptavam o THGBM — ver §3) e
`KMEYH` (bogus/"lixo"; prefixo "KM" é típico de Samsung, não Kioxia). **Bloqueada:** `KLUE` (UFS) — não
adicionar sem spec em `business.kioxia.com` (instrução do operador).

---

## 3. Armadilhas específicas (o durável)

- ⚠ **Magra de prefixo longo intercepta a família de decode completo** — o engine casa o **prefixo mais longo** primeiro. Foi o caso de `THGBMFG`/`THGBMHG` (len 7) capturando antes do `THGBM` (len 5): um PN não confirmado caía na magra → `capacity=None` → INDETERMINADO, em vez de o THGBM decodificar. **Resolvido desativando as magras** (`active:false`) — o THGBM decodifica todos os `THGBMxx`; os known_parts confirmados continuam vencendo. **Sintoma diagnóstico p/ o futuro:** um `THGBM*` aparecendo como "desconhecido" → checar se alguma magra `THGBMxx` está capturando antes.
- ⚠ **`TY890A` é SDRAM, NÃO eMCP** — o prefixo "TY" é compartilhado com o eMCP `TYC`/`TYD`, mas TY890A é SDR SDRAM standalone (confirmado: iFixit PS Vita teardown 2012). Não assumir que todo "TY…" é eMCP.
- ⚠ **"G" em nome Toshiba é Gbit, não GB** (densidade por die). `Gbit ÷ 8 = GB`, depois × dies (ver §2).
- ⚠ **`TYC` (LPDDR2, BGA-162) vs `TYD` (LPDDR3, BGA-221)** — Preduo (Tier 3) confunde os dois; Octopart (Tier 2) prevalece. Distinguir por ball count / fonte Tier-2.
- **pn[14] (sufixo bin/temp) NÃO entra no decode** — o THGBM lê só pn[5] e pn[7:10]. IAs erram alegando que o sufixo `R`/`L` "quebrou" a leitura.
- **Código de lote ≠ spec:** em TYC/TYD, posições de lote diferentes (ex.: `38` vs `26`) = mesmas specs, lote diferente. Não tratar como versão.
- **`8C4` e `8D4` são ambos 32GB** (stack `C` vs `D` = processo diferente, mesma capacidade). Intercambiáveis na triagem.
- **`capacity="1TB"` suportado** (corrigido 2026-06-26): engine + gateway leem TB (`1TB→1024GB`, label `"UFS1TB"`); antes 1TB virava INDETERMINADO. Retrocompatível com GB.

---

## 4. Rentabilidade — princípio (sem valores)

Fonte única: `assess_profitability` + `ProfitabilityConfig` (admin, market-variable). Padrão durável:
**THGBM eMMC** rentável a partir do limiar de capacidade (sem distinção 5.0 vs 5.1 na rentabilidade
binária — embora 5.1 valha ~15–25% mais na revenda; se precisar separar, **propor ao usuário antes de
tocar no engine**). **TYC** (LPDDR2 legado) = NÃO RENTÁVEL; **TYD** (LPDDR3) depende da capacidade. **UFS**
= rentável acima do limiar. **TY890A** (SDRAM) = resíduo. Sem números aqui.

---

## 5. Fontes de pesquisa

Hierarquia (Tier-1→baixo): **kioxia.com / toshiba.semicon-storage.com** (datasheet/product brief, busca
por PN) → Mouser/DigiKey/TrustedParts/Octopart com fonte-fabricante → utmel/censtry/Puris/AIChipLink
(corroboração, nunca fonte única) → Alibaba/OLX/listagem sem datasheet (nunca sem âncora de outro tier).
IAs confundem sufixo de bin com capacidade e alucinam a geração eMMC — cruzar sempre com Octopart/kioxia.com.

> Inventário de famílias/chaves e provenância por-PN (nas `notes`): **`toshiba-kioxia.yaml`**. Comandos,
> convenção completa, rentabilidade, contrato de autoria: **CLAUDE.md**.
