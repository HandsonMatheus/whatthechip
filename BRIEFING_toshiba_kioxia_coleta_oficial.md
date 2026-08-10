# Briefing — Popular Toshiba-Kioxia em massa a partir das fontes OFICIAIS (Tier-1)

> Cole isto no chat da marca **Toshiba-Kioxia**. É uma missão de coleta em LOTE, com a
> disciplina de sempre. Antes de coletar, releia `AUTORIA.md`, `TOSHIBA-KIOXIA.md` e a
> convenção do `CLAUDE.md` — este briefing só adiciona a missão nova por cima do contrato.

## Missão
Coletar o lineup Toshiba-Kioxia (eMMC + UFS — foco no moderno) direto das **fontes oficiais
Kioxia/Toshiba** e entregar **arquivos de submissão estruturados** (known_parts) prontos pro
dono submeter + aprovar. Objetivo: popular **muitos PNs de uma vez, com spec Tier-1** — sem
repetir o erro de dado de distribuidor.

## Regra nº 1 — fonte de spec (INEGOCIÁVEL, a lição do caso N1)
No caso `KMQN10006` (Samsung), **3 distribuidores "concordando" (yoycart/Preduo/Alibaba) diziam
1.5GB — e a leitura do chip físico provou 1GB.** Eles ecoam o mesmo erro entre si.
- **Spec vem SÓ de Tier-1:** Product Briefs / datasheets oficiais Kioxia ou Toshiba
  (`semicon-storage.co.jp`). Octopart/Nexar = Tier-2, só pra **cruzar**.
- **Distribuidor (worldwayelec, Preduo, yoycart, Alibaba, Puris…) = SÓ lista de descoberta**
  ("quais PNs existem"), **NUNCA** fonte de capacidade/RAM. Confundem Gb × GB.
- **Mostre SEMPRE a aritmética:** ex. "24Gb ÷ 8 = 3GB", com a fonte ao lado. Nunca só declarar "3GB".

## Fontes Tier-1 (começar por aqui)
- **e-MMC Product Brief (Kioxia)** — linha eMMC 5.1 (THGBM/THGAM BiCS):
  https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf
- **UFS Product Brief (2.1/3.1)** — THGAF/THGJF:
  https://www.mouser.com/datasheet/3/3711/1/KIOXIA_UFS_Product_Brief.pdf
- **UFS 4.0/4.1:** https://americas.kioxia.com/en-us/business/memory/mlc-nand/ufs4.html
- **Página-mãe eMMC/UFS + Memory Selector:** https://americas.kioxia.com/en-us/business/memory/mlc-nand.html
- **Datasheets individuais** (quando o brief não trouxer a spec) — buscar por PN em kioxia.com / semicon-storage.co.jp.
- **Legados** (THGBM pré-2019 Toshiba, TYC/TYD eMCP, TH58 NAND cru) → arquivos antigos Toshiba
  `semicon-storage.co.jp` — mais espalhado, deixar pra 2ª leva.

## O que coletar por PN
`part_number` · `chip_type` (canônico) · `subtype` (só geração/célula) · `interface` (versão) ·
`capacity` **ou** `emcp_nand`+`emcp_ram` · `confidence: confirmed` · `notes` (a fonte Tier-1
exata: qual brief/datasheet + rev + data).

## Convenção que o PORTÃO força (senão rejeita o registro)
- **eMMC / UFS:** `capacity` em GB · `subtype` VAZIO · `interface` = "eMMC 5.1" / "UFS 3.1".
- **eMCP / uMCP:** `capacity` **VAZIO** · `emcp_nand` = "<interface> <cap>" (ex. "eMMC 5.1 64GB") ·
  `emcp_ram` = "LPDDR<n> <cap>GB" (**tipo ANTES**, ex. "LPDDR3 3GB").
- **NAND cru:** `chip_type` = "NAND Flash" · `subtype` = célula ("SLC/MLC/TLC NAND").
- **`subtype` = SÓ geração/célula** — nunca "+eMMC", densidade, voltagem, "Mobile", package.
- `chip_type` canônico — fonte única `chips/chip_types.py`.

## Disciplina (as regras do dono, endurecidas nesta sessão)
- **Não invente/estime.** PN cuja spec essencial não confirma em Tier-1 → **EXCLUA da submissão**
  (nunca campo em branco nem chutado).
- **Ambíguo** (conflito tipo×spec, tipo-lixo, colisão de chave entre famílias) → **PERGUNTE ao
  dono**, não resolva sozinho.
- **Colete a LINHA/FAMÍLIA inteira** de cada brief de uma vez (não 1 PN por rodada — "de 1 em 1
  a gente termina em 5 anos").
- **Cole a lista no chat** (PN + spec + confidence + fonte), não só entregue o arquivo.
- **Só dados + gramática** (yaml/submissão). NÃO toque em código/testes/infra sem pedir.

## Formato de entrega (arquivo de submissão do `submit_known_parts`)
```yaml
brand: "Toshiba-Kioxia"
known_parts:
  # UFS (usa capacity):
  - part_number: "THGJFAT0T44BAIL"
    chip_type: "UFS"
    subtype: ""
    interface: "UFS 3.1"
    capacity: "128GB"
    confidence: confirmed
    notes: "Kioxia UFS Product Brief Rev.2.0 (2022), tabela BiCS4 128GB 153-ball; datasheet THGJFAT0T44BAIL rev2.00 (2020-08-07). 1024Gbit ÷ 8 = 128GB."
  # eMCP (usa emcp_nand + emcp_ram, capacity VAZIO):
  - part_number: "..."
    chip_type: "eMCP"
    subtype: "LPDDR3"
    interface: ""
    emcp_nand: "eMMC 5.1 64GB"
    emcp_ram: "LPDDR3 4GB"
    confidence: confirmed
    notes: "<brief/datasheet + rev + data + a conta Gb→GB>"
```
Se aparecer **FAMÍLIA nova** (prefixo que ainda não existe no yaml) → isso é GRAMÁTICA:
edita `chips/knowledge/toshiba-kioxia.yaml` + **golden obrigatório** em `chips/tests.py`
(âncora PN + saída esperada: tipo/subtipo/capacidade/rentabilidade).

## Testes ANTES de entregar (o dono cobra sempre)
1. `python manage.py submit_known_parts <arq>.yaml` (dry-run = o PORTÃO) → passa limpo.
2. Se mexeu na gramática: `python manage.py load_brands --brand toshiba-kioxia` (dry-run) + golden verde.
3. Suíte inteira verde: `python manage.py test chips estoque --settings=core.settings_test`.

## Handoff
Entrega o(s) arquivo(s) validado(s) + a lista colada no chat. **O DONO** roda o `--commit` e
**aprova no admin** (four-eyes: quem submete ≠ quem aprova). O chat **NÃO toca em prod**.

## Escopo / expectativa realista
Os briefs cobrem bem o **moderno** (eMMC 5.1, UFS 2.1+) — dá pra popular um bom volume de uma vez.
**Legados** (THGBM antigo, TYC/TYD, TH58) são mais trabalhosos → 2ª leva. Entregue em **lotes por
linha** (ex.: "e-MMC brief" → 1 arquivo; "UFS 3.1 brief" → outro), NÃO tudo num arquivo gigante —
mais fácil de revisar, aprovar e reverter se preciso.
