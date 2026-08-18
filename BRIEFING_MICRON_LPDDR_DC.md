# BRIEFING — Micron: LPDDR em estoque sem capacidade (forma curta `-DC`)

> **Para o chat de marca da Micron.** Data: 2026-08-17. Origem: auditoria
> `audit_sem_specs --brand Micron --estoque` no banco de produção.
>
> ⚠ **Leia a seção 2 antes de começar a pesquisar.** Três caminhos já foram
> testados e fechados — repetir qualquer um deles é rodada perdida.

---

## 1. O problema em números

807 fichas Micron `approved` (confirmed/manual) estão **sem nenhum campo de
capacidade** — e delas dependem **1.102 peças em estoque sem chave de preço**.

| TIPO | PNs | PEÇAS | prioridade |
|---|---:|---:|---|
| LPDDR4X | 338 | 488 | 🔴 alta |
| LPDDR4 | 147 | 201 | 🔴 alta |
| eMCP | 117 | 150 | 🟡 média (27 já resolvem sozinhas) |
| LPDDR5 | 67 | 65 | 🔴 alta |
| uMCP | 20 | 61 | 🟡 média |
| DDR2 | 42 | 81 | ⚪ tipo morto — capacidade não muda veredito |
| MCP | 25 | 43 | ⚪ tipo morto |
| LPDDR3 | 14 | 13 | 🟡 média |
| SSD | 36 | 0 | ⚪ fora do estoque |

**A concentração é o que torna isso viável:** os **40 PNs** da seção 4 somam
**1.002 das 1.102 peças (91%)**. Tirando o tipo morto e o que já se resolve,
sobram **~33 PNs cobrindo ~822 peças**. Não são 807 pesquisas — são ~33.

---

## 2. O que JÁ foi tentado e FALHOU (não repita)

**a) As submissões antigas não cobrem esses PNs.** Busca nos 128 arquivos de
`submissions/`: `MT62F1DAD4DH`, `MT62F1DCD8CZ`, `MT47H32M16HR`, `MT53B2DARN`,
`MT53D4DAUA`, `MT53E1D1AKS` → **zero ocorrências**. Os prefixos `MT62F` e
`MT53E` inteiros → **zero**. Nunca foram pesquisados; vieram do importador.

**b) A API FBGA oficial da Micron devolve registro VAZIO para essa classe.**
Testado em três códigos (`Z9WBD`, `Z8GHC`, `Z9VLP`), todos HTTP 200:

```json
{"part-number":"MT53B1DADS-DC","part-key":"","part-name":"",
 "sub-category":"","fbga-code":"Z9WBD","pageurl":""}
```

O mapeamento FBGA→PN existe; **produto por trás dele, não**. Sem `part-name`
não há densidade a extrair. `fill_capacity_from_micron_api` roda, obtém 200 e
não tem o que gravar — o comportamento está certo, a fonte é que está vazia.

**c) Para o MCP legado a API responde, mas com densidade TOTAL.** Ex.:
`MASSFLASH/MOBILE SDR 1.5G VFBG` — "1.5G" é 1,5 **Gbit** somando NAND + RAM.
Total não se divide em NAND e RAM sem outra fonte, e é tipo morto de todo
jeito. Não gaste rodada com MCP/DDR2.

---

## 3. Anatomia: por que esses PNs são cegos

**⚠ ATUALIZAÇÃO 2026-08-18 — o conjunto é MISTO. Confira a forma antes de
pesquisar:**

| forma | fichas | exemplo | caminho |
|---|---:|---|---|
| curta `-DC` | 510 | `MT53B1DADS-DC`, `MT62F1BAD2DS-DC Y52N` | difícil (ver abaixo) |
| PN COMPLETO | 296 | `MT63G1P3G48D4KQ-017 IT:A` | provavelmente resolve pela API |

O prefixo **MT63G (59 fichas) NÃO é forma curta** — o PN é completo, com bloco de
densidade. O mesmo vale para MT29PZZZ, MT47H, MT29TZZZ, MT29C. Esses 296 são
outro problema, mais fácil, e não foram testados contra a API. **Comece por eles.**

**E o `fbga_code` está preenchido no CAMPO em 807 de 807** (nenhum depende de
código colado no texto do PN) — ou seja, o reverse-lookup de sempre está
disponível para todos. O que a seção 2b mostra é que ele volta VAZIO para a
forma curta; para o PN completo isso nunca foi testado.

**Códigos para testar quando o bloqueio da Micron cair (1 pedido cada):**

```
MT63G  D8KFG  (MT63G1P3G48D4KQ-017 IT:A)   ← PN completo, maior chance
MT62F  Z8FXK  (MT62F1BAD1DS-DC)            ← maior grupo: 223 fichas
MT53E  Z8FSF  (MT53E1BAD4DB-DC)
MT53D  Z9XGM  (MT53D1DADS-DC)
```

Só o MT53B foi testado até agora (Z9WBD/Z8GHC/Z9VLP, 3/3 vazios). Concluir a
classe inteira a partir de um prefixo foi apressado — confirme cada um.

---

**510 das 806 fichas estão na forma curta `-DC`** — não é part number completo.

```
forma COMPLETA (decodifica):   MT53D512M64D8HR-046 WT:B   ← 512M × 64 bits
forma CURTA   (cega):          MT53B1DADS-DC              ← sem bloco de densidade
```

O part number completo da Micron carrega `[Profundidade][Largura]` (ex.:
`512M32` = 512M × 32 bits = 16 Gbit = 2GB). A forma `-DC` não tem esse bloco.
Por isso o tipo aparece (vem do prefixo) e a capacidade não.

**A pergunta central da pesquisa é:** *o que a forma curta identifica, e qual a
densidade de cada uma?* Se a resposta vier por PN, entregue por PN. Se aparecer
um padrão, ótimo — acelera —, mas **a entrega continua sendo known_parts, um
por PN, no arquivo de submissão**.

### Inventário por prefixo (só o que está sem capacidade)

| PREFIXO | PNs | tipos |
|---|---:|---|
| MT62F | 223 | LPDDR4X ×156, LPDDR5 ×67 |
| MT53E | 86 | LPDDR4X |
| MT53D | 77 | LPDDR4 |
| MT53B | 62 | LPDDR4 |
| MT63G | 59 | LPDDR4X |
| MT52L | 14 | LPDDR3 |
| MT62FDA / MT62DC / MT53DC | 21 | LPDDR4X / LPDDR4 |

---

## 4. A fila — 40 PNs = 91% das peças paradas

🔴 = pesquisar · ⚪ = tipo morto, ignorar · ✅ = já resolvido, ignorar

| # | PART NUMBER | TIPO | PEÇAS | |
|---:|---|---|---:|---|
| 1 | MT62F1DAD4DH-DC Y62P | LPDDR4X | 50 | 🔴 |
| 2 | MT62F1DCD8CZ-DC | LPDDR4X | 40 | 🔴 |
| 3 | MT29C1G12MAURAJA-6 IT | MCP | 39 | ⚪ |
| 4 | MT47H32M16HR-25E L:G | DDR2 | 38 | ⚪ |
| 5 | MT53B2DARN-DC | LPDDR4 | 38 | 🔴 |
| 6 | MT53D4DAUA-DC | LPDDR4 | 38 | 🔴 |
| 7 | MT53E1D1AKS-DC | LPDDR4X | 38 | 🔴 |
| 8 | MT53B2DANK-DC X | LPDDR4 | 37 | 🔴 |
| 9 | MT62F2DADBZA-DC Y52N | LPDDR4X | 36 | 🔴 |
| 10 | MT53E4DCHJ-DC | LPDDR4X | 34 | 🔴 |
| 11 | MT30AZZZDDC5TOAV-023 W.27F | uMCP | 32 | 🟡 cap. não mapeada |
| 12 | MT62F1DAD4EK-DC Y5BN | LPDDR5 | 32 | 🔴 |
| 13 | MT53E1BHDDNQ-DC DD18K | LPDDR4X | 31 | 🔴 |
| 14 | MT62FDB1AFK-DC | LPDDR4X | 31 | 🔴 |
| 15 | MT53E8DCHJ-DC | LPDDR4X | 30 | 🔴 |
| 16 | MT30AZZZEDC5TPAW-023WES.27G | uMCP | 29 | 🟡 |
| 17 | MT53D4DANW-DC | LPDDR4 | 29 | 🔴 |
| 18 | MT29TZZZ5D6JKFRL-107 WH.96R | eMCP | 29 | ✅ |
| 19 | MT53E8D1CEG-DC | LPDDR4X | 28 | 🔴 |
| 20 | MT53B2DATQ-DC | LPDDR4 | 26 | 🔴 |
| 21 | MT53E4D1BSQ-DC | LPDDR4X | 26 | 🔴 |
| 22 | MT29TZZZ4D4BKERL-125 W.94M | eMCP | 24 | ✅ |
| 23 | MT62F8DAAY-DC | LPDDR4X | 19 | 🔴 |
| 24 | MT29PZZZ4D4CKESK-18 WF.94H | eMCP | 18 | 🟡 |
| 25 | MT29PZZZ8D4RKKEQ-3 W ES.6V4 | eMCP | 18 | 🟡 |
| 26 | MT47H32M16HR-25:G | DDR2 | 18 | ⚪ |
| 27 | MT62F2BAD8DV-DC Y63N | LPDDR4X | 18 | 🔴 |
| 28 | MT29TZZZ8D5JKETS-107 W.95Q | eMCP | 17 | ✅ |
| 29 | MT53E8D1DGS-DC | LPDDR4X | 16 | 🔴 |
| 30 | MT62FDACWA-DC | LPDDR4X | 16 | 🔴 |
| 31 | MT47H32M16HR-5E ES:F | DDR2 | 15 | ⚪ |
| 32 | MT63G2MADBKE-DC T62M | LPDDR4X | 15 | 🔴 |
| 33 | MT29VZZZAC8FQKSL-053 W.G8F | eMCP | 13 | 🟡 |
| 34 | MT52L8DBQC-DC | LPDDR3 | 13 | 🔴 |
| 35 | MT62F2DAD8GJ-DC X Y5BN | LPDDR4X | 13 | 🔴 |
| 36 | MT62F1DAD8CZ-DC | LPDDR5 | 12 | 🔴 |
| 37 | MT62F1DAD8DN-DC Y6CP | LPDDR4X | 12 | 🔴 |
| 38 | MT62F1DBD4CZ-DC | LPDDR4X | 12 | 🔴 |
| 39 | MT29VZZZ7D7DQKWL-062 W.97Y | eMCP | 11 | 🟡 |
| 40 | MT53D2DBNP-DC | LPDDR4 | 11 | 🔴 |

Lista completa: `micron_sem_specs.csv` (rode com `--estoque` para as
quantidades saírem no arquivo).

---

## 5. Regras da casa que valem aqui

- **Tier-1 obrigatório** para capacidade: datasheet/ordering guide da Micron ou
  Octopart. **Distribuidor NUNCA é fonte de capacidade.**
- **Mostre a aritmética** `Gb ÷ 8 = GB` sempre, com 2 fontes independentes
  batendo. Declarar "4GB confirmado" sem a conta não passa.
- **Excluir é melhor que adivinhar**: PN sem fonte Tier-1 fica FORA do arquivo,
  sinalizado à parte — nunca campo em branco ou chutado.
- **Cole a lista no chat** (PN + spec + confidence), não só o arquivo.
- **Não toque em código, yaml ou testes.** Este chat entrega dado.

## 6. Como entregar

Arquivo `submissions/micron_lpddr_dc_<data>.yaml`, campo de capacidade
**preenchido de verdade** (`capacity` para LPDDR discreto — não descreva a
capacidade dentro do `subtype`, foi esse o erro da família MT29C em julho e por
isso aqueles PNs seguem sem número até hoje).

Comandos a entregar junto:

```
python manage.py submit_known_parts submissions/<arquivo>.yaml
python manage.py submit_known_parts submissions/<arquivo>.yaml --commit --fill-empty
```

O `--fill-empty` é obrigatório aqui: essas fichas **já estão aprovadas** e sem
ele o submit as pula em silêncio (foi exatamente o que aconteceu em julho).
Depois de aprovar no admin, o dono roda `resnapshot_lote --all --commit` para os
lotes pegarem a classificação nova.
