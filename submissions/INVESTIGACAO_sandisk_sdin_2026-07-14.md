# Investigação — família SanDisk SDIN (eMMC iNAND legado), a partir do PN SDIN4C24G (2026-07-14)

> ✅ **Resultado: 21 known_parts submetidos, 18 deles `confidence=confirmed`** — direto de **3
> datasheets oficiais SanDisk** que localizei e li na íntegra (não mirror/resumo — abri o PDF
> completo, com cabeçalho, histórico de revisão e tabela "Ordering Information"). É a melhor
> cobertura Tier-1 já obtida numa investigação desta marca (SDAD, investigado ontem, não tinha
> NENHUM datasheet público). Arquivo: `sandisk_sdin_2026-07-14.yaml`.

## 0. O gatilho

Debug do estoque, 14/07/2026 09:25:05, PN `SDIN4C24G`: família genérica `SDIN` (priority 80,
fallback — "a família mais comum na esteira" per `SANDISK.md`), `known_exact=false`,
`profitable=INDETERMINADO`. Fuzzy suggestions do motor: `SDIN5C14G`, `SDIN5C28G`, `SDIN5D24G` —
sinal de que o padrão é `SDIN` + [dígito][letra][dígito] + sufixo de capacidade.

## 1. Metodologia

4 buscas paralelas independentes (fontes oficiais SanDisk/WD; distribuidores Tier-1/2; busca direta
do PN âncora; varredura ampla de cluster via broker) + verifiquei **3 datasheets oficiais eu mesmo**
por fetch direto (não confiei só no relato dos agentes — abri os PDFs, li as tabelas "Ordering
Information"/"Capacity for User Data" byte a byte). Nenhum arquivo do repositório foi tocado pelos
agentes (lição do incidente de ontem — proibi Edit/Write explicitamente em cada prompt desta vez).

## 2. Achado principal: a família SDIN cobre 3 GERAÇÕES DE PROTOCOLO distintas, não só "eMMC 4.5/5.0/5.1"

A `sandisk.yaml` descrevia a família como cobrindo "eMMC 4.5, 5.0 e 5.1". Os 3 datasheets oficiais
que li mostram uma cronologia mais rica e, num ponto, **desatualiza** a descrição:

| Geração (1º dígito) | Protocolo real | Doc oficial | Ano |
|---|---|---|---|
| **2** (`SDIN2xx`) | **SD 1.1/2.0 + SPI** — NÃO é eMMC, é anterior ao padrão MMC | 80-36-00592 Rev 1.2 | jul/2007 |
| **4** (`SDIN4xx`, inclui o PN âncora) | eMMC (geração exata NÃO confirmada — provável transição ~2008-2009) | nenhum localizado publicamente | ~2008-2009 |
| **5** (`SDIN5xx`) | **e.MMC 4.41** (JESD84-A441) | 80-36-03433 Rev 1.3 | dez/2010 |
| **7** (`SDIN7DP2`) | **e.MMC 4.51 "Ultra"** (JESD84-B451) | 80-36-03494 Rev 1.3 | fev/2013 |

Ou seja: a "geração 2" nem é eMMC de verdade, e existe um buraco documental real na "geração 4"
(inclusive o PN do seu caso) — nenhuma das 3 fontes oficiais que achei cobre o `SDIN4C2`
especificamente. Atualizei o `tip` da família e o `SANDISK.md` com essa cronologia.

## 3. Os 3 datasheets oficiais (verifiquei cada um por fetch direto — não é relato de agente)

### A) Doc 80-36-00592, Rev 1.2, jul/2007 — "SanDisk iNAND (JEDEC Package) Data Sheet"
`https://media.digikey.com/pdf/Data%20Sheets/M-Systems%20Inc%20PDFs/SDIN2C_B_Rev_Jul_2007.pdf`
— hospedado pela DigiKey, cabeçalho/copyright/patentes SanDisk Corporation autênticos. Tabela 15
"Ordering Information": 6 PNs (512MB→8GB). Protocolo: SD 1.1/2.0 + SPI, 169-ball JEDEC BGA.

### B) Doc 80-36-03433, Rev 1.3, dez/2010 — "SanDisk iNAND e.MMC 4.41 I/F Data Sheet"
`https://media.digikey.com/pdf/Data%20Sheets/M-Systems%20Inc%20PDFs/iNAND_e.MMC_4.4_I_F.pdf`
— idem, DigiKey. Tabela 12 "Ordering Information" (10 PNs, 2GB→64GB) **+** Tabela 9 "Capacity for
User Data" com a contagem exata de LBA/bytes por PN (ex.: `SDIN5C2-4G` = 7.729.152 LBA =
3.957.325.824 bytes) — o nível de precisão mais alto que já usei numa submissão desta marca.
"X2"/"X3" na tabela = tecnologia NAND (2 bits/célula MLC vs. 3 bits/célula), não é sufixo de PN.

### C) Doc 80-36-03494, Rev 1.3, fev/2013 — "SanDisk iNAND Ultra e.MMC 4.51 I/F Data Sheet"
`https://www.bulcomp-eng.com/datasheet/SDIN7DP2-4G%20(BGA153)%20-%20Datasheet%201.pdf`
— mirror de terceiro, mas cabeçalho/copyright/patentes/histórico de revisão SanDisk idênticos aos
outros dois (autenticidade consistente). Tabela 12 "Ordering Information" + Tabela 9 "Capacity for
User Data": 2 PNs (4GB, 8GB), 153-ball, 11.5×13×1.0mm.

## 4. O cluster do PN âncora (SDIN4C2) — SEM datasheet oficial, mas com triangulação forte

Diferente dos outros 3 grupos, não achei datasheet pra geração "4". A evidência disponível NÃO é
distribuidor/marketplace simples (que seria Tier-3) — é **engenharia real verificada**:

- **TI E2E (fórum de engenharia da Texas Instruments, fetch direto):** thread de 2010-2011 de um
  engenheiro integrando `SDIN4C2-4G` numa placa DM365 (TI DaVinci, câmera/vídeo industrial),
  citando "the data sheet for the SDIN4C2-4G device" — confirma uso real em produto embarcado E
  a existência de um datasheet do fabricante (que não localizei online, mas que o engenheiro tinha
  em mãos em 2010). `https://e2e.ti.com/support/processors-group/processors/f/processors-forum/124680/`
- **Elnec (fabricante de programadores de chip, fetch direto):** lista `SDIN4C2-4G-U [FBGA169]` e
  `SDIN4C2-8G-U [FBGA169]` como dispositivos suportados, com adaptador de hardware específico —
  precisa de pinout real pra funcionar, não é revenda. `elnec.com/en/device/SanDisk/`
- **iFixit (fetch direto, texto real das páginas, não resumo):** **"SanDisk SDIN4C2-16G 16GB Flash
  memory"** — Motorola Droid Bionic Teardown E **"SanDisk SDIN4C2 16GB MLC NAND flash"** — Nexus S
  Teardown. Confirma explicitamente, em prosa técnica (não título de anúncio), que o sufixo `-16G`
  desta família = 16GB — estabelece a convenção pro cluster inteiro.
  `ifixit.com/Teardown/Motorola+Droid+Bionic+Teardown/6449` e `.../Nexus+S+Teardown/4365`
- **serviceemmc.com (lista de compatibilidade de técnicos, cross-ref de dispositivo):**
  `SDIN4C2-8G = I9000` (Samsung Galaxy S).
- **7+ distribuidores independentes** (veswin, jotrin, win-source, ic-components, kynix, ariat-tech)
  convergem na mesma escada de capacidade 2G/4G/8G/16G, package 169FBGA.

**Submeti como `confidence=manual`** (não `confirmed` — não é datasheet do fabricante; não
`distributor` — a evidência é mais forte que revenda simples, é engenharia/teardown verificado):
`SDIN4C24G` (o PN do seu caso), `SDIN4C28G`, `SDIN4C216G`.

**Ficou de fora:** `SDIN4C22G` (só distribuidor + 1 stencil eBay, sem a mesma triangulação dos
outros 3 — nenhuma fonte forte confirma especificamente essa capacidade) e `SDIN4C1*`
(**conflito não resolvido**: um agente concluiu que não existe / é confusão com `SDIN5C1`; outro
achou 4 PNs com specs de pacote reais no omo-ic.com como família distinta. Sem consenso entre as
próprias buscas, não decidi sozinho — fica para confirmação futura).

## 5. ⚠ Golden test — 3 PNs confirmados hoje já são âncora de INDETERMINADO

`chips/tests.py::_SD_GOLDEN` tem `SDIN5C116G`, `SDIN5C14G`, `SDIN5C18G` congelados como
`("eMMC", "", "", "", "", "INDETERMINADO")` (grafia sem traço = mesma normalização). Depois de
aprovar esses 3 known_parts no admin, o golden vai ficar desatualizado (o PN vai passar a ter
capacidade real e sair de INDETERMINADO) — é esperado, mas o `characterize_baseline --diff` vai
acusar a mudança; é o dono quem atualiza o `tests.py` (fora do meu escopo tocar `.py`).

## 6. O que ficou de fora deste round (backlog, não é "excluído para sempre")

Fonte: varredura ampla via `omo-ic.com/tags/SDIN.html` (301 entradas brutas, técnica que já tinha
funcionado bem no round SDAD). Achados reais mas **só broker** (sem datasheet, sem forum/teardown
de apoio) — candidatos pra uma rodada futura, não submetidos hoje:
- **`SDIN3xx`** (SDIN3C2-2G/4G/16G, SDIN3F1-64G) — geração entre a 2 (SD/SPI) e a 4, protocolo não
  confirmado (descrições dizem "MMC" genérico).
- **`SDIN8xx`** (SDIN8DE1/2/4, SDIN8DR1, SDIN8CE4 — dezenas de PNs, muitos com variante automotiva
  `-XA`/`-XI`/industrial `-I`/`-A`) — eMMC 4.51 HS200, geração mais nova que a 7.
- **`SDIN9xx`** (SDIN9DW4/5, SDIN9DS2) — geração mais nova ainda, specs de alta performance.
- **`SDIN4C1*`, `SDIN4C22G`** — ver §4.

**Nota sobre variantes de grade (`-A` automotivo, `-I`/`-XI`/`-XA` industrial/temp. estendida, `-Q`
amostra):** são a MESMA capacidade/produto em qualificação diferente, não capacidades distintas —
não tratei cada uma como known_part separado (inflaria o catálogo sem ganho — o campo de
capacidade é idêntico ao PN base). Se precisar diferenciar por temperatura no futuro, é decisão do
dono sobre se vale a pena.

## 7. Fontes completas
- 3 datasheets oficiais: ver §3.
- https://e2e.ti.com/support/processors-group/processors/f/processors-forum/124680/
- https://www.elnec.com/en/device/SanDisk/SDIN4C2-4G-U+%5BFBGA169%5D/
- https://www.ifixit.com/Teardown/Motorola+Droid+Bionic+Teardown/6449
- https://www.ifixit.com/Teardown/Nexus+S+Teardown/4365
- https://www.serviceemmc.com/2020/08/support-ic-emmcufs-all-brandnew-update.html
- https://www.omo-ic.com/tags/SDIN.html (varredura de cluster, backlog §6)

Arquivos internos consultados: `chips/knowledge/sandisk.yaml` (família SDIN), `SANDISK.md`,
`chips/tests.py` (`_SD_GOLDEN`).
