# Investigação — SanDisk `SD5DH` (eMMC legado), a partir do PN SD5DH26A4G (2026-07-14)

> ✅ **Resultado: 3 known_parts submetidos, todos `manual`.** Cluster inteiro mapeado (4 die-codes:
> `24A`/`24C` eMMC puro já conhecidos, `26A` **eMCP** — decisão do dono, ver §2 — e `24H` fraco
> demais pra submeter). Corrigi uma imprecisão no tip da família (capacidade "-8G" não existe de
> verdade no `SD5DH`, pertence a uma família IRMÃ `SD5D` sem o H, achada de bônus — ver §4). Arquivo:
> `sandisk_sd5dh_2026-07-14.yaml`.

## 0. O gatilho

Debug do estoque, 14/07/2026 15:44:50, PN `SD5DH26A4G`: família `SD5DH` já conhecida (eMMC legado,
era 2012-2013), mas `known_exact=false`, `confidence=estimated`, `profitable=INDETERMINADO` — o
die-code "26A" não estava entre os 3 já documentados no tip (24=24nm, letra A/C/F=revisão), e a
própria interface da família já estava marcada como "estimada, sem datasheet Tier-1".

## 1. Metodologia

2 buscas paralelas independentes (verificação direta do tipo/specs do PN âncora; varredura do
cluster completo de die-codes) + minhas próprias buscas diretas antes de despachar. Achado central
gerou uma AMBIGUIDADE real de tipo (eMMC vs eMCP) que sinalizei ao dono ao vivo — decisão registrada
no §2.

## 2. `SD5DH26A-4G`: eMMC puro ou eMCP? — decisão do dono: **eMCP**

Evidência CONTRADITÓRIA entre fontes:
- **A favor de eMCP:** eBay (`ebay.com/itm/115970049765`) descreve explicitamente "**eMCP** ( 4GB
  eMMC + 6G LPDDR )". Um substituto Samsung **pino-a-pino confirmado** do mesmo chip nos MESMOS
  aparelhos (`KMJ5U000WA-B409`/`KMJJS000WM-B409`, achado numa lista de equivalência de reparo
  independente, kiagsm.ir) é **eMCP genuíno**, verificado no nosso próprio índice de confiança
  Puris (`puris.net/archives/2719`: "KMJ5U000WM-B409 4+6 153ball eMCP-D1 Samsung") e corroborado
  por Alibaba ("...Lpddr1 Emcp Memory..."). Um substituto pino-a-pino só funciona se as duas peças
  tiverem a MESMA arquitetura elétrica — o que só faz sentido se o SanDisk também embutir RAM.
- **A favor de eMMC puro:** AliExpress (2 anúncios) e 2 lojas russas (vkgsm.ru, axeum.ru) chamam
  só de "EMMC NAND memory flash", sem mencionar LPDDR/RAM.
- **Coincidência de RAM que reforça eMCP:** os 3 aparelhos que usam este chip (ver §3) têm **RAM
  TOTAL documentada de exatamente 768MB** (GSMArena/PhoneMore, fonte de specs de aparelho, nada a
  ver com revenda de componente) — e 6Gb (a "RAM" do anúncio eBay) ÷ 8 = **768MB exatos**. Muito
  específico pra ser coincidência.
- **Sem datasheet oficial** pra desempatar (nenhum encontrado pra família inteira).

Apresentei essa contradição ao dono ao vivo (2026-07-14). **Decisão: tratar como eMCP**, aceitando a
triangulação (substituto Samsung confirmado + aritmética de RAM batendo) mesmo sem fonte Tier-1
direta — `confidence=manual`, com a metodologia registrada por extenso na `notes` do known_part.

## 3. Achado novo: dispositivo do `26A` — HTC Desire X, Huawei U8950, LG P715

Os 3 dispositivos originais catalogados no tip (S5301/S6810/S6802) são todos do die-code `24A`/`24C`
— o `26A` corresponde a um cluster de aparelhos DIFERENTE, todos 2012, ~768MB RAM:
- **HTC Desire X (T328e/T328w)** — AliExpress (2×) + vkgsm.ru (loja russa).
- **Huawei U8950 / Ascend G600** — kiagsm.ir.
- **LG Optimus L7 II (P715)** — kiagsm.ir.

## 4. Correção ao tip: capacidade "-8G" NÃO existe de verdade no `SD5DH` (com H)

O tip atual diz "Capacidade típica: 4GB-8GB... Sufixo declarativo: -4G=4GB · -8G=8GB". Busca
exaustiva (die-codes 20-29 × letras A-G, ~15 distribuidores) **não achou NENHUM PN "-8G" dentro do
prefixo `SD5DH` estrito** — toda ocorrência real usa exclusivamente "-4G". O "-8G" que existe de
verdade pertence a uma **família IRMÃ, `SD5D` (SEM o H)**, achada de bônus (ver §5) — prefixo
diferente, portanto grammar diferente. Corrigi o tip pra não overclaim mais uma capacidade sem PN
real por trás.

## 5. Achado de bônus (backlog, fora do escopo de hoje): família irmã `SD5D` (sem H)

`SD5D` (sem H) é uma família **totalmente separada**, **eMCP confirmado**, com ball-count DIFERENTE
(FBGA162 em pelo menos 1 membro, vs FBGA153 do `SD5DH`) — não existe no nosso yaml:
- `SD5D14A-4G` — "4GB eMMC iNAND + 4G LPDDR", FBGA153.
- `SD5D28B-4G` / `-8G` — "4GB eMMC4.41 + 8G LPDDR", **FBGA162**, compatível com aparelhos Lenovo.
- `SD5D28C-16G` — existência confirmada, specs não verificadas.

Como hoje NÃO é o prefixo do caso (que é `SD5DH`, com H), **não submeti known_parts nem criei
família pra isso** — mesma disciplina aplicada ontem ao `SDINHDL6`/`SDINFDQ6` (achados de relance,
fora do escopo do dia, registrados pra rodada futura). PNs já mapeados acima pra não perder o
trabalho.

## 6. known_parts submetidos (3)

| PN | Tipo | Capacidade | Confidence | Dispositivo |
|---|---|---|---|---|
| SD5DH24A4G | eMMC | 4GB | manual | Samsung GT-S6802 |
| SD5DH24C4G | eMMC | 4GB | manual | Samsung GT-S5301, GT-S6810 |
| **SD5DH26A4G** (PN do caso) | eMCP | NAND 4GB / RAM LPDDR1 768MB | manual | HTC T328e/w, Huawei U8950, LG P715 |

## 7. O que ficou de fora

- **`SD5DH24H-4G`** — só 1 distribuidor (hkinventory), sem segunda fonte independente, sem
  dispositivo correlacionado. Backlog.
- **Combinações não encontradas:** `SD5DH24B/D/E/F/G`, `SD5DH26B/C/D/E/F/G`, e todas as séries
  `SD5DH2{0,1,2,3,5,7,8,9}*` — "não encontrado" ≠ "não existe", só não apareceu na busca.
- **Significado dos 2 dígitos (24/26):** não confirmado por fonte direta. Hipótese "processo em nm"
  (24nm) não se sustenta pro "26" (26nm não é nó SanDisk documentado) — fica sem explicação.
- **Família `SD5D` (sem H)** — ver §5, backlog completo pra rodada futura.

## 8. ⚠ Golden test

`SD5DH24A4G` já é âncora de INDETERMINADO em `chips/tests.py::_SD_GOLDEN`. Após aprovação no admin,
vai desatualizar (esperado) — `characterize_baseline --diff` acusa, atualização é do dono.

## 9. Fontes completas
- https://www.ebay.com/itm/115970049765 (SD5DH26A-4G, "eMCP")
- https://www.aliexpress.com/item/3pcs-lot-SD5DH26A-4G-EMMC-NAND-memory-flash-with-firmware-for-HTC-Desire-X-T328E/32702231029.html
- https://vkgsm.ru/produkt/mikroshema-nand-flash-sd5dh26a-4g-htc-desire-x
- https://axeum.ru/product/mikroshema-nand-flash-sd5dh26a-4g-htc-desire-x
- https://www.puris.net/archives/2719 (substituto Samsung KMJ5U000WM-B409, eMCP-D1 confirmado)
- https://kiagsm.ir/similar-emmcs/ (lista de equivalência — device Huawei U8950, LG P715)
- https://www.serviceemmc.com/2020/08/support-ic-emmcufs-all-brandnew-update.html (24A=S6802, 24C=S5301/S6810)
- https://www.netcomponents.com/sitemap/SD5D28B-4G.html e SD5D14A-4G.html (família irmã, backlog)
- https://forums.sandisk.com/t/whats-the-difference-between-these-decode-part-numbers/35429 (confirma ausência de decoder público)

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SD5DH), `SANDISK.md`,
`chips/tests.py` (`_SD_GOLDEN`, ver §8).
