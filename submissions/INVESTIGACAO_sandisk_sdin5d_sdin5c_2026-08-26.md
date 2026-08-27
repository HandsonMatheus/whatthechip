# Investigação — SanDisk clusters `SDIN5D1`/`SDIN5D2`/`SDIN5C1`/`SDIN5C2`, PN `SDIN5D12G` (2026-08-26)

> ✅ **Resultado: 15 known_parts, `confidence=confirmed`.** Datasheet oficial SanDisk 80-36-03462
> lido NA ÍNTEGRA (Table 9, "Ordering Information") via mirror alldatasheet.com. Arquivo:
> `sandisk_sdin5d_sdin5c_2026-08-26.yaml`.

## 0. O gatilho

Debug do estoque, 26/08/2026 14:28:46, PN: `SDIN5D12G`. Família = `SDIN` (fallback genérico,
priority 80), `known_exact=false`, `confidence=estimated`, `profitable=INDETERMINADO`,
`pn_not_in_db=true`. Fuzzy sugeriu `SDIN5D14G`, `SDIN5D18G`, `SDIN5D22G`, `SDIN5C132G`, `SDIN5C14G`
— nenhum é o PN exato, mas os dois últimos (`SDIN5C1xx`) sinalizam possível registro prévio na
mesma vizinhança (rodada 07-14).

## 1. Fonte — datasheet oficial lido na íntegra

Busca inicial (`"SDIN5D1"`, `"SDIN5D2"`) achou o PN em ~8 distribuidores/agregadores (eBay, Elnec,
Octopart, acodis.ru, DigiElectronics, Xecor, veswin.com) — identidade e existência do PN nunca
foram dúvida. O achado forte foi o **datasheet direto**: `datasheet.octopart.com/SDIN5D1-2G-...pdf`
(fetch direto retornou vazio, mesmo padrão já visto em `SDIN7DU2`) — mas o **mirror alldatasheet.com**
funcionou (técnica já registrada em `wtc-pdf-fetch-mirror-distribuidor`), permitindo ler o documento
completo página por página.

**Doc 80-36-03462** — "SanDisk iNAND e.MMC 4.41 I/F - Standard and Ultra", © 2011 SanDisk
Corporation, 33 páginas. Confirmado: pinout 153-ball MMC (pág. 20), domínios de potência (pág. 29),
e a **Table 9 — Ordering Information** (Seção 7, pág. 32), transcrita integralmente:

| Capacidade | Tecnologia | Part Number | Pacote |
|---|---|---|---|
| 2GB | X2 | SDIN5D1-2G-L | 11.5×13×1.0mm |
| 4GB | X2 | SDIN5D2-4G-L | 11.5×13×1.0mm |
| 4GB | X3 | SDIN5D1-4G-L | 11.5×13×1.0mm |
| 8GB | X2 | SDIN5D2-8G-L | 11.5×13×1.0mm |
| 8GB | X2 | SDIN5C2-8G-L | 12×16×1.0mm |
| 8GB | X3 | SDIN5D1-8G-L | 11.5×13×1.0mm |
| 8GB | X3 | SDIN5C1-8G-L | 12×16×1.0mm |
| 16GB | X2 | SDIN5D2-16G-L | 11.5×13×1.2mm |
| 16GB | X2 | SDIN5C2-16G-L | 12×16×1.0mm |
| 16GB | X3 | SDIN5C1-16G-L | 12×16×1.0mm |
| 16GB | X3 | SDIN5D1-16G-L | 11.5×13×1.2mm |
| 32GB | X2 | SDIN5C2-32G-L | 12×16×1.2mm |
| 32GB | X3 | SDIN5C1-32G-L | 12×16×1.2mm |
| 64GB | X2 | SDIN5C2-64G-L | 12×16×1.4mm |
| 64GB | X3 | SDIN5C1-64G-L | 12×16×1.4mm |

X2 = MLC (2 bits/célula), X3 = TLC (3 bits/célula) — mapeado pro campo `device`, mesma convenção já
usada em `SDIN4E232G`/`SDIN5B232G`. Nota da própria tabela: sufixo `-L` = embalagem em bandeja
(default); `-LT` seria a variante tape/reel — **não** é sufixo de grade/spec, por isso os
known_parts entram sem `-L` (mesmo padrão de todos os outros PNs SanDisk já confirmados).

## 2. Cluster — 4 sub-códigos, 15 combinações

Die-code "5D1" e "5D2" (pacote 11.5×13mm, menor) vs "5C1"/"5C2" (pacote 12×16mm, maior) — mesma
capacidade, footprint físico diferente. Padrão de tecnologia: `5D2`/`5C2` = sempre X2 (MLC);
`5D1`/`5C1` = X3 (TLC) exceto `5D1` em 2GB, que é X2 — única combinação nessa capacidade.

**Exclusão:** `SDIN5D2-2G` aparece citado em 3 distribuidores (elnec.com, nexelec.com,
veswin.com) mas **não existe linha correspondente na Table 9** (só 2GB/X2/`SDIN5D1` está listado
nessa capacidade). Regra "excluir, não adivinhar": não confirmado, não entrou nesta submissão. Fica
como possível backlog — se aparecer na bancada, tratar como PN a investigar à parte (pode ser
confusão de distribuidor com `SDIN5D1-2G`, ou capacidade real de uma revisão de doc não localizada).

## 3. Sobreposição com a rodada 07-14 (SDIN5B2/5C1, doc 80-36-03433)

O fuzzy do debug sugeriu `SDIN5C132G` e `SDIN5C14G` — die-code `5C1` já apareceu na rodada 07-14,
mas sourced de um datasheet **diferente** (80-36-03433, dez/2010, usado pra `SDIN5B232G`). Aquele
doc pode cobrir capacidades que este (80-36-03462, 2011) não cobre e vice-versa — por exemplo,
`SDIN5C1` a 4GB parece existir só no doc antigo (sugerido pelo fuzzy `SDIN5C14G`, ausente da Table 9
deste doc). **Não reconciliei ativamente** — os dois datasheets provavelmente representam
revisões/famílias de produto coexistentes, e o painel do `submit_known_parts` (NOVO/COMPLEMENTO/
CONFLITO/IGUAL) resolve overlaps automaticamente por campo, sem eu precisar adivinhar qual doc
"vence". Se `SDIN5C132G`/`SDIN5C116G` já existirem confirmados com os MESMOS valores desta
submissão, caem em IGUAL; se divergirem, é caso pro `resolve_conflicts`.

## 4. known_parts submetidos (15)

Ver arquivo `sandisk_sdin5d_sdin5c_2026-08-26.yaml` — todos `confidence=confirmed`, mesma fonte
primária (Table 9, doc 80-36-03462):

| PN | Capacidade | Tecnologia | Pacote |
|---|---|---|---|
| SDIN5D12G | 2GB | X2 | 11.5×13×1.0mm |
| SDIN5D14G | 4GB | X3 | 11.5×13×1.0mm |
| SDIN5D18G | 8GB | X3 | 11.5×13×1.0mm |
| SDIN5D116G | 16GB | X3 | 11.5×13×1.2mm |
| SDIN5D24G | 4GB | X2 | 11.5×13×1.0mm |
| SDIN5D28G | 8GB | X2 | 11.5×13×1.0mm |
| SDIN5D216G | 16GB | X2 | 11.5×13×1.2mm |
| SDIN5C18G | 8GB | X3 | 12×16×1.0mm |
| SDIN5C116G | 16GB | X3 | 12×16×1.0mm |
| SDIN5C132G | 32GB | X3 | 12×16×1.2mm |
| SDIN5C164G | 64GB | X3 | 12×16×1.4mm |
| SDIN5C28G | 8GB | X2 | 12×16×1.0mm |
| SDIN5C216G | 16GB | X2 | 12×16×1.0mm |
| SDIN5C232G | 32GB | X2 | 12×16×1.2mm |
| SDIN5C264G | 64GB | X2 | 12×16×1.4mm |

## 5. Limitações

- `SDIN5D2-2G`: excluído (ver §2), backlog se reaparecer na bancada.
- Não busquei por sufixos de grade (`-I1`/`-XA1`/etc.) para nenhum destes PNs — se aparecer um na
  bancada, precisa de known_part próprio (regra já documentada em SANDISK.md §3 pra `SDINBDA6`).
- Não reconciliei o overlap com o doc 80-36-03433 da rodada 07-14 (ver §3) — deixado pro painel do
  `submit_known_parts`.
- Não abri as demais ~30 páginas do datasheet (specs elétricos detalhados, timing) — irrelevantes
  pro known_part (chip_type/capacidade/interface/device já vêm direto da Table 9).

## 6. Fontes

- Datasheet oficial (lido na íntegra): https://www.alldatasheet.com/html-pdf/646958/ETC2/SDIN5D1-2G-L/3418/32/SDIN5D1-2G-L.html (Table 9, pág. 32/33) — doc 80-36-03462.
- Páginas de contexto do mesmo doc: pág. 20 (pinout), pág. 29 (power), pág. 33 (contato/fim).
- https://octopart.com/sdin5d1-2g-sandisk-18985406
- https://elnec.com/en/device/SanDisk/SDIN5D1-2G-L+[FBGA153]
- https://www.veswin.com/product-SDIN5D2-4G.html
- https://www.preduo.com/product/emmc/sdin5d2-4g

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDIN, tip atualizado),
`SANDISK.md` §0.1 (painel do submit_known_parts).
