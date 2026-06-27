# SUMÁRIO DE PESQUISA — TOSHIBA / KIOXIA TIER 1
**Data:** 2026-06-26 · **Projeto:** WhatTheChip · **Regra:** fontes Tier 1 exclusivas (kioxia.com / toshiba.semicon-storage.com)

**Resultado:** **39 PNs novos confirmados** em product briefs oficiais Kioxia (todos `confidence=confirmed`), nenhum duplicando a Seção 2.

| Categoria | Prefixo | Novos PNs | Fonte Tier 1 |
|---|---|---:|---|
| UFS 3.1/4.0/4.1 | THGJF | 18 | UFS Product Brief Rev.3.0 (2025) + Rev.2.0 (2022) |
| UFS 2.1 (consumer + automotive) | THGAF | 11 | UFS Product Brief Rev.2.0 + Automotive Product Brief Rev.2.0 (2020) |
| eMMC 5.1 BiCS (**prefixo novo**) | THGAM | 6 | e-MMC Product Brief Rev.2.0 (2023) |
| eMMC 5.1 automotive (variante BAB) | THGBMJG | 4 | Automotive Product Brief Rev.2.0 (2020) |
| **TOTAL** | | **39** | |

Maior ganho: **UFS sai de 0 → 29 PNs no banco**, e surge um **prefixo eMMC inteiramente novo (THGAM)** com 6 PNs.

---

## Fontes Tier 1 utilizadas (4 PDFs oficiais Kioxia)

1. **UFS Product Brief Rev.3.0 (2025)** — `https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf`
2. **UFS Product Brief Rev.2.0 (2022)** — `https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf`
3. **e-MMC Product Brief Rev.2.0 (2023)** — `https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf`
4. **Automotive Managed Flash Solutions Product Brief Rev.2.0 (Out/2020)** — `https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf`

> `americas.kioxia.com` e `www.kioxia.com` são subdomínios de `kioxia.com` → **Tier 1** conforme Seção 1 do prompt.

---

## ENCONTRADO

- **UFS THGJF (18 PNs):** prefixo UFS da Kioxia **confirmado na própria kioxia.com** (não Samsung — KLUC é que é Samsung; aqui o prefixo é THGJF). Densidades 128GB→1TB, UFS 3.1 / 4.0 / 4.1, consumer grade. As tabelas de PN dos dois UFS Product Briefs (2022 e 2025) listam cada PN explicitamente com capacidade e versão UFS.
- **UFS THGAF (11 PNs):** geração anterior **UFS 2.1**. 2 consumer (32/64GB, brief 2022) + 9 automotive AEC-Q100 Grade 2 (16→256GB, brief 2020). Confirma a Prioridade 6 (THGAF existe e tem specs em Tier 1).
- **eMMC THGAM (6 PNs):** **prefixo eMMC novo, não coberto pela gramática THGBM atual.** eMMC 5.1, BiCS FLASH 3D, 16→128GB, 153-ball BGA. Séries V (VG7/VG8/VG9/VT0) e S (SG9/ST0). Listados na tabela "Consumer Grade" do e-MMC Product Brief (idêntico em Rev.1.1/2022 e Rev.2.0/2023).
- **eMMC THGBMJG automotive (4 PNs):** variantes **BAB** (automotive Grade 2) dos THGBMJG industriais que já existem no banco em variante **BAU**. 8→64GB, eMMC 5.1, FG NAND, -40 a 105°C. PNs distintos (pn[13:15] = B7/B8 vs U7/U8) → não são duplicatas.

## NÃO ENCONTRADO (pesquisado, negativo confirmado)

- **eMCP TYC / TYD (Prioridade 5):** nenhuma fonte Tier 1. Buscas em `toshiba.semicon-storage.com` e `kioxia.com` por "TYC eMCP LPDDR2" retornaram apenas produtos não-memória (motor drivers, fotoacopladores). **Confirma o aviso do prompt:** "Tier 1 quase impossível para eMCP". Os 4 eMCP da Seção 2 seguem sem upgrade Tier 1.
- **THGBM com pn[5] = D / G / M / 4 (Prioridade 2):** nenhum brief Kioxia atual lista THGBMDG/THGBMGG/THGBMMG/THGBM4G. As séries eMMC THGBM ativas na Kioxia hoje são apenas N, T, U (consumer FG NAND) e J (industrial/automotive). A linha BiCS nova migrou para o **prefixo THGAM**, não para novas letras pn[5] de THGBM.
- **THGBM > 128GB (Prioridade 3):** inexistente. Os product briefs afirmam explicitamente que **eMMC vai até 128GB**; acima disso a Kioxia direciona para UFS. Não há eMMC 256GB Tier 1.
- **Chaves THGBM bloqueadas 4D4 / 6A2 / 6A4 / 8D2 e Tier-3 4D1 / 5D2 / 6D1 (Prioridades 3-4):** sem âncora Tier 1. São de eras antigas Toshiba (THGBM4G*/BG*/DG*, ~2013-2015) que não aparecem nos briefs Kioxia atuais e cuja documentação saiu do ar com a migração (ver discrepância abaixo).
- **UFS THGAF pré-2019 em domínio Toshiba (Prioridade 6):** o domínio `toshiba.semicon-storage.com` **não hospeda mais nenhum produto de memória** — o catálogo geral 2016 (`catalog_en_20160301_ALQ00214.pdf`) não contém um único PN THGBM/THGAF/TYC/eMMC/UFS. Toda a memória Toshiba foi transferida para `kioxia.com` no rebrand de 2019. THGAF foi, porém, recuperado via briefs Kioxia (ver ENCONTRADO).

## DISCREPÂNCIAS / ARMADILHAS ENCONTRADAS

1. **`brand_name` = "Kioxia" no output vs Brand "Toshiba" no banco.** O prompt (Seção 6) pede pré-2019=Toshiba / pós-2019=Kioxia, mas **todas as 4 fontes Tier 1 são documentos Kioxia (2020-2025)** — não existe mais fonte Tier 1 da era Toshiba. Por isso marquei **todos os 39 como `Kioxia`**. ⚠️ **O banco de produção usa Brand `Toshiba` para todos os THGBM** (ver `TOSHIBA-KIOXIA.md`). **Antes de rodar `fix_known_parts`, decida:** (a) criar Brand `Kioxia` no admin/seed, **ou** (b) trocar `brand_name` para `Toshiba` (busca por substituição no `.py`/`.csv`). O campo é trivialmente remapeável; nenhuma spec depende dele.
2. **THGAF é geração de transição.** A linha UFS 2.1 THGAF nasceu na era Toshiba (~2017-2018) mas só é documentada (Tier 1) nos briefs Kioxia. O silkscreen físico pode trazer "TOSHIBA" **ou** "KIOXIA" conforme a data de fabricação. Tratado como Kioxia por causa da fonte.
3. **THGAM é prefixo novo — a gramática THGBM NÃO o decodifica.** `pn[0:5]="THGAM"` ≠ `"THGBM"`. Como entrego KnownParts com `capacity` explícita e `confidence=confirmed`, eles classificam corretamente mesmo sem família. Mas se quiser **cobertura de cauda longa** para THGAM, será preciso uma `ChipFamily` THGAM nova em `populate_toshiba.py` (fora do escopo desta pesquisa — só Tier 1).
4. **THGJF e THGAF (UFS) também são prefixos sem família.** Mesmo caso: cobertos como KnownPart, mas sem decode posicional. Como UFS standalone tem capacidade no próprio PN, os KnownParts bastam para o gateway de estoque.
5. **512GB UFS automotive EXCLUÍDO por ambiguidade.** A linha de 512GB do Automotive Brief aparece como `THGAFBT2T83BABI5` com pacote 14.0×18.0mm, mas a extração de texto fundiu o número de nota de rodapé (⁵ = "New product") com o PN, deixando a fronteira ambígua (`THGAFBT2T83BABI` vs `...BABI5`, 15 vs 16 chars). Por R1 (zero alucinação) **não incluí**. Precisa de confirmação visual do PDF.
6. **Variantes B vs E (UFS automotive).** Diferem só pela nota 4 ("max pre-load 100% da user area"); mesma capacidade/tipo/pacote. Ambas incluídas como PNs distintos (o operador pode ler qualquer uma).
7. **`package` vazio para UFS.** Os briefs UFS dão só dimensões em mm, **não o ball-count BGA**. Por R3 (specs explícitas), deixei `package=""` para UFS e pus as dimensões em `notes`. Para eMMC o brief diz "153 ball BGA" explicitamente → `package="BGA-153"`.
8. **Páginas HTML de produto são JS-rendered** (`business.kioxia.com/.../ufs.html` voltou vazia no fetch). Os **PDFs de product brief** são a fonte Tier 1 confiável e legível por máquina — fonte preferida desta pesquisa.

## RECOMENDAÇÕES PARA PRÓXIMA SESSÃO

1. **Decidir o mapeamento de Brand** (Kioxia vs Toshiba) e ajustar os 39 registros antes do `fix_known_parts --dry-run`.
2. **Confirmar visualmente o 512GB UFS automotive** (`THGAFBT2T83BABI5`/`THGAFBT2T83BABI`) abrindo o Automotive Product Brief PDF — então adicionar como 40º PN.
3. **Avaliar criar `ChipFamily` THGAM** (e opcionalmente THGJF/THGAF UFS) em `populate_toshiba.py` para cobertura de cauda longa — exigiria mapear a estrutura posicional desses prefixos (pesquisa de gramática, não de PN).
4. **eMCP TYC/TYD continua sem Tier 1.** Se precisar enriquecer, terá de aceitar Tier 2 (Octopart/Mouser) ou datasheet sob NDA — não há saída Tier 1 pura.
5. **Datasheets individuais sob login.** Os briefs trazem a tabela de PNs; specs elétricas detalhadas (timing, BiCS gen exata) ficam em datasheets "available upon request" no portal Kioxia. Para `nand_gen` (BiCS3/4/5) seria preciso esse acesso — por ora deixei `nand_gen=""` (só "BiCS FLASH 3D" na nota, que é o que o brief afirma).

---

## Verificação adversarial (Seção 9 do prompt) — PASSOU

- ☑ Cada PN tem `source_url` de domínio Tier 1 (`kioxia.com`).
- ☑ Cada spec (capacity, interface) consta **literalmente** na tabela de PN do brief — não inferida.
- ☑ `capacity` em GB/TB (briefs já reportam em GB/TB; sem conversão Gb necessária).
- ☑ Sem eMCP no output → regra de ordem `emcp_ram` não aplicável.
- ☑ `subtype` ≤ 3 palavras, sem versão/capacidade/bus width ("UFS Kioxia", "eMMC Kioxia").
- ☑ Nenhuma duplicata da Seção 2 (checado programaticamente: 0 colisões).
- ☑ Prefixo UFS verificado como **Kioxia** (THGJF/THGAF) na própria fonte, não Samsung.
- ☑ Sumário documenta os negativos (eMCP, THGBM D/G/M/4, >128GB, chaves bloqueadas).
