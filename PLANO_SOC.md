# PLANO_SOC.md — Estudo para tornar `SoC` um tipo comercial

> **Status: ESTUDO. Nenhuma linha de código foi alterada.** Este documento é o levantamento
> que precede a decisão do dono, no mesmo formato do `PLANO_FX.md` / `PRECIFICACAO.md`.
> Origem: lote de SoCs Spreadtrum (ver `SPREADTRUM.md`). Data: **2026-08-17**.
>
> Regra da casa respeitada (`wtc-nao-modificar-codigo-sem-perguntar`): chat entrega
> estudo + diff proposto; o dono decide e roda.

---

## 1. Resumo executivo

Tornar `SoC` comercial é uma mudança **pequena em código e grande em consequência**. O
sistema já tem o molde pronto — o **K9** (2026-08-14) é exatamente isto: um tipo *plano*,
sem marca, sem capacidade, sem geração, com preço fixo ¥/unidade. Copiar o K9 é o caminho
seguro.

**Três achados que mudam o desenho:**

| # | Achado | Consequência |
|---|---|---|
| 1 | 🟢 **Blast radius é ZERO.** Nos 7.843 PNs do `baseline_pre_t6.json` **não existe um único registro com `chip_type="SoC"`.** (Só NOR Flash 4, MCP 32, OneNAND 1.) | Virar a chave **não muda o veredito de nenhum chip do catálogo atual**. É aditivo puro. Risco de regressão ≈ 0. |
| 2 | 🔴 **A categoria `"catalog"` NÃO pode sair.** Se `SoC` mudar de categoria, o `subtype` **sequestra o `chip_type`** — provado empiricamente abaixo. | `commercial=True` **mantendo** `category="catalog"`. É o mesmo padrão do K9 (`nand_raw` + `commercial=True`). |
| 3 | 🟡 **`SSD` e `K9` NÃO aparecem na área do comprador.** `_NAV_KINDS` (`pricing/views.py:121`) só tem emcp/umcp/lpddr/emmc/ufs/ddr. | ✅ **DECIDIDO 2026-08-17:** SSD e K9 **entram** no painel (trabalho A, independente e prioritário); SoC fica **admin-first** e entra depois. Ver §7. |
| 4 | 🔴 **O comprador exige 套片 (conjuntos casados).** SoC + PMIC + RF são uma plataforma, não peças soltas — `SPREADTRUM.md §4.9`. | Pode transformar o escopo de **1 tipo comercial** em **3**. Bloqueado até ele responder a pergunta desambiguadora (§8.5.3). |

**Decisões que travam a implementação** (§10): modelo de preço · o SoC aparece na área do
comprador ou só no admin · uma caixa só ou uma por geração (3G/4G).

---

## 2. Diagnóstico — como o sistema trata `SoC` hoje

`chips/chip_types.py:118`:

```python
"SoC": ChipTypeSpec("catalog", "none", "indeterminado", commercial=False),
```

Traduzindo campo a campo, e o que cada um causa hoje:

| Campo | Valor hoje | Efeito prático |
|---|---|---|
| `category` | `"catalog"` | Está em `_TYPE_WINS_CATS` (`chip_types.py:169`) → **o `chip_type` manda sobre o `subtype`**. Também libera `subtype` DESCRITIVO no portão (`schema.py:160`, `knowledge/convention.py:74`) |
| `label_kind` | `"none"` | `_compute_destination` não tem branch → cai no fallback → **sem caixa** |
| `profit_family` | `"indeterminado"` | `assess_profitability` devolve INDETERMINADO → **estado âmbar no gateway**, nunca "Rentável: sim" |
| `commercial` | `False` | Fora de `COMMERCIAL_TYPES`; o **handshake de rentabilidade pula o tipo** (`tests.py:762`) |
| `aliases` | *(vazio)* | `spec_for("CPU")` devolve **`None`** — o operador digitar "CPU" não resolve pra nada |

E no pricing: `label_kind="none"` não está em `KINDS`, então `derive_price_key`
(`pricing/engine.py:210`) devolve `NO_KEY` com o motivo *"tipo 'SoC' fora do mercado de
preço (triagem descarta)"*. **Sem preço, sem caixa, sem cotação.** Consistente — o sistema
não está quebrado, está declarando que ainda não decidimos.

---

## 3. 🔴 A armadilha nº 1 — a categoria `"catalog"` é o que segura o tipo

Isto foi **provado rodando o registro real** (`chips/chip_types.py` + `chips/conventions.py`
importados puros, fora do Django):

```
=== HOJE (category="catalog", que ESTÁ em _TYPE_WINS_CATS) ===
  canonical_chip_type('SoC', 'LPDDR3 + eMMC 5.1')          -> 'SoC'      ✅
  canonical_chip_type('SoC', 'LPDDR2/LPDDR3 + eMMC 4.5')   -> 'SoC'      ✅

=== SE SoC mudasse para uma categoria NOVA (ex.: "logic") fora de _TYPE_WINS_CATS ===
  canonical_chip_type('SoC', 'LPDDR3 + eMMC 5.1')          -> 'LPDDR3'   ❌ SEQUESTRO
  canonical_chip_type('SoC', 'LPDDR2/LPDDR3 + eMMC 4.5')   -> 'LPDDR2'   ❌ SEQUESTRO
```

**Por quê:** o passo 2 do `canonical_chip_type` (`chip_types.py:216-223`) procura uma
geração de RAM no `subtype` e a deixa vencer o `chip_type`. É o comportamento correto para
DRAM (`("RAM","DDR3 SDRAM") → "DDR3"`), e é **catastrófico** para SoC — porque o `subtype`
natural de um SoC **menciona memória**: "LPDDR3 + eMMC 5.1" é literalmente a especificação
publicada do SC9832E pela UNISOC.

Um SC9832E viraria um chip **LPDDR3** no catálogo: tipo errado, caixa errada, preço errado,
rentabilidade errada. E passaria em todos os portões, porque a forma está correta — é erro
de **fato**, a única classe que `AUTORIA.md §8` admite que nenhum sistema pega.

> ### ✅ Regra derivada (inegociável)
> **`SoC` continua com `category="catalog"`.** Só mudam `label_kind`, `profit_family`,
> `commercial` e `aliases`. Se um dia alguém quiser uma categoria própria (`"logic"`), ela
> **tem que ser adicionada a `_TYPE_WINS_CATS`** no mesmo commit — senão reintroduz o bug.
>
> Bônus de manter `catalog`: o portão continua aceitando `subtype` **descritivo**
> (`schema.py:159-162`). Fora de `catalog`, o portão normalizaria "Quad A53 1.4GHz LTE Cat4"
> → mutilaria a descrição. O K9 escapa disso por ter `subtype=""`; o SoC **quer** descrição.

---

## 4. O precedente K9 — a planta baixa completa

O K9 entrou em **11 pontos de toque**. Cada linha abaixo é o endereço exato do que o SoC
precisa espelhar.

| # | Arquivo:linha | O que o K9 fez | O que o SoC faria |
|---|---|---|---|
| 1 | `chips/chip_types.py:77` | `"K9": ChipTypeSpec("nand_raw","k9","k9")` | mudar a entrada `SoC` (§5) |
| 2 | `chips/engine.py:1219` | branch `if _fam == "k9"` no `assess_profitability` | branch `if _fam == "soc"` → veredito definitivo |
| 3 | `chips/engine.py:1400-1435` | curto-circuito do **pseudo-PN** `"K9"` antes de família/banco/fuzzy | ❌ **NÃO se aplica** — SoC tem PN legível (§6.1) |
| 4 | `estoque/views.py:238` | `_TYPE_PSEUDO_PNS = {'K9'}` (exceção ao mínimo de 4 chars) | ❌ não se aplica |
| 5 | `estoque/views.py:493-496` | `if kind == 'k9': return 'K9','k9'` no `_compute_destination` | `if kind == 'soc': return 'SOC','soc'` |
| 6 | `pricing/models.py:69,82` | `KIND_K9='k9'` + entrada em `KIND_CHOICES` | `KIND_SOC='soc'` idem |
| 7 | `pricing/models.py:103` | `_GEN_RULE[KIND_K9] = re.compile(r'^$')` | idem (ou `^(3G\|4G)$` na opção B) |
| 8 | `pricing/models.py:88-92` | **ausente** de `KIND_UNIT` de propósito (GB/Gb não se aplica) | idem — comentar o porquê |
| 9 | `pricing/models.py:240` | campo `Buyer.k9_rmb_each` + **migração `0023_buyer_k9_rate.py`** | `Buyer.soc_rmb_each` + migração `0024_*` |
| 10 | `pricing/convention.py:62,160` | letra `'k9':'K'` + linha fundadora `('k9','','1','',1)` | letra `'soc':'I'` + `('soc','','1','',1)` |
| 11 | `pricing/engine.py:218,282,440,529` | `derive_price_key` chave plana + `_k9_quote` + 2 caminhos de cotação | espelhar 1:1 |
| +1 | `pricing/admin.py:43` | campo no fieldset do Buyer | idem |
| +1 | comando `seed_category_codes` | carrega a `FOUNDING_TABLE` | rodar após anexar a linha |

**A letra:** A=eMCP · B=eMMC · C=uMCP · D=UFS · E=DDR · F=LPDDR · G=SSD · K=K9.
H e R são reservadas. Pela regra de `pricing/convention.py:32` ("tipo novo pega a próxima
letra livre"), **SoC = `I`** → caixa **`I-01`**. (O K9 desviou para `K` por escolha explícita
do dono; aqui não há motivo mnemônico para desviar.)

---

## 5. O diff proposto do `chip_types.py` (o coração da mudança)

```python
# ── Catálogo — sem caixa comercial; classificação/documentação ───────────
...
    # SoC (dono, 2026-08-XX): AP + baseband integrados — o "cérebro" do celular.
    # ⚠ category CONTINUA "catalog" DE PROPÓSITO, mesmo sendo comercial: é o que
    #   mantém o tipo em _TYPE_WINS_CATS. Sem isso, um subtype legítimo como
    #   "LPDDR3 + eMMC 5.1" (spec oficial do SC9832E) SEQUESTRA o chip_type e o
    #   chip vira LPDDR3 — erro de FATO que passa em todos os portões.
    #   Bônus: 'catalog' libera subtype DESCRITIVO no portão (schema.py:159).
    #   Precedente da independência dos flags: K9 é nand_raw + commercial=True.
    "SoC": ChipTypeSpec("catalog", "soc", "soc", commercial=True,
                        aliases=("soc", "cpu", "ap", "baseband",
                                 "processor", "system on chip")),
```

**Sobre os aliases** — hoje `spec_for("CPU")` devolve `None`. Com o alias, o operador
digitando "CPU" na bancada e o comprador escrevendo "CPU" na planilha caem no mesmo token
canônico. Verificado na simulação: `canonical_chip_type('CPU','quad A7') -> 'SoC'`.

⚠️ **Cuidado com `"ap"`**: alias de 2 letras é agressivo — pode casar com lixo. Recomendo
entrar **sem** `"ap"` na primeira rodada e só adicionar se aparecer na prática.

---

## 6. O que QUEBRA — os tripwires, com endereço

Nenhum deles é surpresa: são exatamente as travas que o `AUTORIA.md §5` promete. Todos
falham **ANTES** do deploy, na suíte.

| Trava | Onde | O que acontece | Ação |
|---|---|---|---|
| 🔴 **Teste explícito** | `chips/tests_convention.py:159` — `assertFalse(is_commercial("SoC"))` | **falha na hora** | inverter para `assertTrue` no mesmo commit (é o registro da decisão) |
| 🔴 **Vocabulário fechado** | `chips/tests_convention.py:21-25` — `_LABEL_KINDS` e `_PROFIT_FAMILIES` | `"soc"` não está nas listas → falha | anexar `"soc"` nas duas |
| 🟡 **Handshake de rentabilidade** | `chips/tests.py:744-770` | com `commercial=True` o tipo **entra no laço**; se `assess_profitability` não tiver branch → INDETERMINADO → **falha** | criar o branch `_fam == "soc"` no `chips/engine.py` |
| 🟢 **Golden obrigatório** | `chips/tests.py:801` | só dispara para **família de prefixo novo em yaml ativo**. Não haverá `spreadtrum.yaml` com família (ver `SPREADTRUM.md §2.4`) → **não dispara** | nada — mas se um dia criar família `SC`, aí exige âncora |
| 🟡 **check_translations** | `chips/management/commands/check_translations.py` | qualquer string nova marcada precisa existir nos **4 catálogos** (pt-br/es/en/zh-hans), senão a suíte fica vermelha | traduzir `help_text` do campo + rótulos de UI. ⚠ o **código de caixa `I-01` NUNCA traduz** (canônico) |
| 🟢 **characterize --diff** | comando | prova que nada mudou nos PNs existentes | **deve dar diff = 0** — dado o blast radius zero (§1), qualquer diff ≠ 0 é bug |
| 🟡 **RLS / migração** | `wtc-runpython-rls-guc-plataforma` | migração que faz backfill em tabela com RLS precisa do GUC | a migração `0024` é **AddField puro, sem RunPython** → não se aplica. Se virar backfill, aplicar a regra |

---

## 7. ✅ A área do comprador — DECIDIDO pelo dono (2026-08-17)

O levantamento mostrou que `pricing/views.py:121` traz

```python
_NAV_KINDS = ('emcp', 'umcp', 'lpddr', 'emmc', 'ufs', 'ddr')
```

— ou seja, **`ssd` e `k9` nunca apareceram no painel do comprador**. Não foi decisão de produto;
foi consequência de os dois terem preço-*fórmula* no registro `Buyer` em vez de linhas de grid.

### Decisão do dono

> **1. `SSD` e `K9` DEVEM entrar no painel do comprador.** É correção de uma lacuna existente,
> **independente do SoC** — vale ser um commit próprio, que pode ir ao ar antes de qualquer coisa
> de SoC.
>
> **2. `SoC` NÃO entra no painel agora** — fica **admin-first**. Entra depois, quando houver
> preço estabelecido com o Wu Quan.

### O que isso implica tecnicamente (trabalho A — SSD/K9 no painel)

Este é **um plano separado**, não uma fase do SoC. Os pontos de toque:

| Ponto | Arquivo:linha | Problema |
|---|---|---|
| Navegação | `pricing/views.py:121` | anexar `'ssd'`, `'k9'` a `_NAV_KINDS` |
| 🔴 **Validação do save** | `pricing/views.py:514` | `tier_unit not in ('GB','Gb')` → **rejeita**. O K9 tem `tier_unit=''` e o SSD é ¥/GB linear, sem faixa. **Este é o nó do problema** |
| Grid vs fórmula | `pricing/engine.py:440,529` | os dois **desviam** para `_ssd_quote`/`_k9_quote` antes de consultar o grid — a tela precisa editar o campo do `Buyer`, **não** criar linhas de `Price` |
| `KIND_UNIT` | `pricing/models.py:88-92` | `k9` está ausente **de propósito**; a tela não pode assumir que todo kind tem unidade |
| Template | `partner_kind.html` | hoje renderiza uma **matriz de faixas**. Para SSD/K9 a tela certa é **um campo só** (¥/GB e ¥/unidade) |
| i18n | `check_translations` | rótulos novos nos 4 idiomas |

> ⚠️ **A forma da tela é diferente, não é "mais uma linha na lista".** eMCP/DDR/eMMC são **grids de
> faixa de capacidade**; SSD e K9 são **um número só**. Enfiar os dois na mesma tela é o caminho
> curto que gera bug — o desenho honesto é o `partner_kind` detectar o kind e renderizar
> **"tabela de faixas"** ou **"taxa única"**.
>
> Isso quer dizer que o trabalho A **precisa do seu OK sobre a UI** antes de eu escrever código.
> Sugiro: um bloco "Taxas" no topo do painel, com SSD (¥/GB) e K9 (¥/unidade) como dois campos —
> separado da navegação por tipo, que continua sendo de grid. Assim o SoC entra nesse mesmo bloco
> depois, sem redesenho.

### O que isso implica para o SoC (trabalho B)

Nada muda nas fases §9 — o SoC nasce com `Buyer.soc_rmb_each` editável **só no admin**. Quando o
preço estiver estabelecido, entrar no painel é **anexar uma linha** ao bloco de taxas que o
trabalho A já terá criado. Custo marginal ≈ zero. É a ordem certa.

---

## 8. Modelo de preço — as três formas, e por que SoC é diferente

**O problema de fundo:** todo o pricing do WTC é keado por `(kind, gen, tier_value,
tier_unit)`, e o `tier` é sempre **capacidade**. **SoC não tem capacidade.** É a mesma
situação do K9 — e por isso o K9 é o molde certo.

### Opção A — ¥ fixo por unidade *(padrão K9)*
Chave plana `('soc','',1,'')`. Uma caixa: **I-01**. Um campo: `Buyer.soc_rmb_each`.

- ✅ Mais simples, já provado, ~1 dia
- ✅ Honesto com a realidade: sem referência de preço, começar com um número único
- ❌ Trata SC7727S (3G, 2014, dual-core) e SC9832E (4G, 2018, 64-bit) **pelo mesmo preço** —
  e a evidência de mercado diz que são propostas diferentes

### Opção B — ¥ por **era do modem** (3G / 4G)
Chave `('soc','3G',1,'')` e `('soc','4G',1,'')`. Duas caixas: **I-01** e **I-02**.
`_GEN_RULE[KIND_SOC] = re.compile(r'^(3G|4G|5G)$')`.

- ✅ Captura o eixo de valor que a pesquisa achou (demanda de reuso concentra-se pós-2018;
  LTE tem parque instalado maior)
- ✅ Só 2 caixas — não explode a operação
- ✅ Encaixa direto na Opção II do §7 (grid com 2 linhas)
- ❌ Introduz um vocabulário de "geração" que **não é RAM** — precisa de decisão explícita
  para não confundir com `DDR3`/`LPDDR4`
- ❌ 🔴 **Exige saber a era de cada PN** — e a Spreadtrum **não tem gramática de decode**
  (`SPREADTRUM.md §2`). A era só existe se o PN estiver como `known_part` confirmado.
  Chip sem registro → sem era → sem caixa
- ❌ Precisa de uma decisão-limite: e o `SC7727SE` (3G de 2016)? E um SoC 5G futuro?

### Opção C — ¥ por part number
- ❌ **Rejeitar.** Quebra a arquitetura: a chave de preço nunca teve dimensão de PN. Seria
  uma tabela nova, um caminho de resolução novo e um universo de manutenção (cada PN novo =
  uma cotação). Registro aqui só para fechar a questão.

> **Recomendação: A agora, com B documentada como upgrade.** A migração A→B é aditiva
> (a linha `I-01` vira "3G" e nasce `I-02` = "4G"), **desde que** nenhuma caixa física tenha
> sido rotulada ainda. Se o dono achar que o Wu Quan **já** vai diferenciar 3G/4G, vale
> nascer em B — trocar depois de existir caixa física é caro.

---

## 8.5 Catalogar SoC no banco — quais specs coletar (e quais NÃO)

Pergunta do dono: *"podemos identificar esses chips e catalogá-los com suas especificações? o que
esses chips têm de specs que devemos coletar?"*

**Resposta curta: sim, e sem nenhuma migração.** O `KnownPart` já comporta um SoC — desde que
você aceite que a maioria dos campos dele é de memória e simplesmente **não se aplica**.

### 8.5.1 O mapa campo a campo do `KnownPart`

| Campo | SoC usa? | O quê |
|---|---|---|
| `part_number` | ✅ **é tudo** | `SC9832E`. É a única coisa que o comprador compra. Sem gramática, o PN **é** a identidade |
| `brand` | ✅ | `Spreadtrum` (⚠ decidir: uma marca ou duas com alias `UNISOC` — ver §8.5.4) |
| `chip_type` | ✅ | `SoC` |
| `subtype` | ✅ **livre** | 🔑 `category="catalog"` libera **subtype DESCRITIVO** (`schema.py:159`) — o portão **não** normaliza. Aqui cabe a linha legível: `Quad Cortex-A53 1.4GHz · Mali-T820 MP1 · LTE Cat4 · 28nm` |
| `device` | ✅ **alto valor** | Aparelhos de origem: `Nokia C2 / Meizu C9 / ZTE Blade A3 2019`. É **como o comprador procura** e como a bancada confere |
| `notes` | ✅ **obrigatório** | Fonte Tier-1 + o **套片** (§8.5.3). Regra da casa: `confidence` sem fonte na `notes` o revisor barra |
| `source_url` | ✅ | link do press release / unisoc.com |
| `confidence` | ✅ | `confirmed` para os 5 PNs com fonte oficial |
| `capacity` | ❌ | SoC não tem capacidade |
| `density_gbit` / `density_gb` | ❌ | idem |
| `emcp_ram` / `emcp_nand` | ❌ | é composto NAND+RAM — SoC não é |
| `interface` | ❌ | é largura de barramento (`x8`/`x16`) de DRAM |
| `fbga_code` | ❌ | código FBGA é da Samsung/Micron |
| `family` | ❌ | não haverá `ChipFamily` (§2 do `SPREADTRUM.md`) |

> ⚠️ **Regra da casa, sem exceção** (`wtc-excluir-nao-adivinhar-known-part`): campo que não se
> aplica fica **vazio**. Nunca `"N/A"`, nunca `"—"`, nunca estimado "pra documentar".

### 8.5.2 O que realmente vale coletar — ordenado por valor comercial

Vale separar **spec técnica** de **spec comercial**. Elas não coincidem.

| # | Dado | Vale? | Por quê |
|---|---|---|---|
| 1 | **Part number** | 🟢 essencial | O comprador compra por PN. É o único eixo de match com uma necessidade de reparo |
| 2 | **Era do modem (3G/4G)** | 🟢 essencial | É o **eixo de valor** (demanda de reuso concentra-se pós-2018) e o candidato natural a dimensão de preço na opção B (§8) |
| 3 | **套片 — PMIC e RF casados** | 🟢 **essencial** | O comprador **exige** (ver `SPREADTRUM.md §4.9`). Sem isso, o lote pode não ter mercado |
| 4 | **Aparelhos de origem** (`device`) | 🟡 alto | É como o comprador enxerga demanda ("preciso de chip de J2 2016") |
| 5 | **Ano de lançamento** | 🟡 médio | Proxy da linha "pós-2018"; cabe no `subtype` ou `notes` |
| 6 | Núcleos / clock / GPU / nó | 🟠 baixo | Interessante tecnicamente, **quase irrelevante comercialmente**. Ninguém compra SoC recuperado por GFLOPS. Vai no `subtype` porque é barato, não porque decide preço |
| 7 | Package / ball count / pitch | 🟡 médio | Não decide preço, mas decide **reballing** (o estêncil é por padrão de esferas). Agora temos dado Tier-1 via BOM da FCC (`SPREADTRUM.md §4.6`) |
| 8 | Bandas LTE | 🔴 **não coletar** | Não existe por SoC — dependem do RF e da homologação do aparelho |

**Conclusão honesta:** o instinto é catalogar núcleos, GPU e nanômetros porque é o que as fichas
técnicas mostram. Mas o que move preço aqui é **PN + era + 套片 + condição**. Colete o resto
porque é barato, não porque vale.

### 8.5.3 🔴 Onde mora o 套片 — e por que ele NÃO é um problema de catálogo

O comprador quer conjuntos casados (`SPREADTRUM.md §4.9`). Isso cria uma tentação: criar um campo
de "chip companheiro" no `KnownPart`. **Não faça.** A distinção que resolve:

| Pergunta | Camada | Onde vive |
|---|---|---|
| *"Com que PMIC o SC9832E casa?"* | **CATÁLOGO** — fato universal e estável da plataforma | `notes` do `KnownPart` (custo zero, sem migração) |
| *"Eu TENHO o PMIC casado, e quantos?"* | **ESTOQUE** — fato local, muda todo dia | ainda **não existe** no sistema |

A exigência do comprador é a **segunda** pergunta. E a segunda pergunta não é resolvida com um
campo de texto — ela precisa que **PMIC e RF sejam eles próprios tipos com caixa e contagem**, o
que hoje não são (`PMIC` está em `chip_types.py` como catálogo/não-comercial, exatamente como o
SoC estava).

> **Consequência de plano:** se o Wu Quan de fato comprar **conjuntos**, o escopo não é
> "SoC comercial" — é **"SoC + PMIC + RF comerciais"**, três tipos, três letras (`I`, `J`, e a
> próxima), três caixas. É uma decisão bem maior que a deste documento, e ela depende inteiramente
> da resposta dele à pergunta desambiguadora (`DOSSIE_SPREADTRUM_BUYER_EN.md §7.1`).
>
> **Recomendação: não construa nada de 套片 antes dessa resposta.** Registre o pareamento na
> `notes` (grátis) e espere.

### 8.5.4 Duas decisões menores, mas que travam a submissão

1. **`Brand` = "Spreadtrum" ou "UNISOC"?** É a mesma empresa (rebrand em 13/06/2018), e a marcação
   física varia por lote. *Recomendo* **uma marca só, `Spreadtrum`**, com `UNISOC` mencionado na
   `notes` — o `Brand` do WTC é chave de agrupamento, não fato histórico. Duas marcas partiriam o
   catálogo em dois pela data de fabricação, o que não ajuda ninguém.
2. **O `subtype` descritivo entra em qual idioma?** Ele **não** é traduzido pelo i18n (é dado, não
   string de UI), então fica congelado no que for escrito. *Recomendo inglês técnico*
   (`Quad Cortex-A53 1.4GHz · Mali-T820 MP1 · LTE Cat4 · 28nm`) — é o idioma da fonte e o que o
   comprador lê.

### 8.5.5 Os 5 PNs prontos para submissão (quando as fases liberarem)

`SC7727S` · `SC7727SE` · `SC7731C` · `SC9830I` · `SC9832E` — todos com fonte Tier-1 registrada no
`SPREADTRUM.md §10`.
**Excluídos de propósito:** `SC98301` (não existe) e `SC7715T` (existência não confirmada).

⚠️ **Ordem:** a submissão é a **F6** — depois de existir caixa e preço. Submeter antes faz o chip
cair como INDETERMINADO âmbar no gateway, sem destino para o operador (§9).

---

## 9. Fases — cada uma com seu portão

Ordem escolhida para que **nada chegue ao operador antes de ter destino comercial**.

| Fase | O que faz | Portão (verde antes de seguir) |
|---|---|---|
| **F0** | Este documento + decisões do §10 | ✍️ dono responde |
| **F1** | `chip_types.py`: `SoC` comercial + `label_kind="soc"` + `profit_family="soc"` + aliases | `python manage.py test chips.tests_convention` — **vai falhar** em `:159` e nos vocabulários. Corrigir os 3 e ficar verde |
| **F2** | `chips/engine.py`: branch `_fam == "soc"` no `assess_profitability` | `RentabilidadeHandshakeTests` verde |
| **F3** | `estoque/views.py`: branch `kind == 'soc'` no `_compute_destination` | teste de destino + **`characterize_baseline --diff` = 0** |
| **F4** | `pricing`: `KIND_SOC`, `_GEN_RULE`, letra `I`, linha fundadora, `Buyer.soc_rmb_each` + migração `0024`, `_soc_quote`, admin | `pricing` tests verdes + `seed_category_codes` idempotente |
| **F5** | i18n: `help_text`, rótulos | `check_translations` exit 0 nos 4 idiomas |
| **F6** | `submit_known_parts` dos 5 PNs Spreadtrum confirmados | dry-run do portão + **dono roda `--commit` + aprova** (four-eyes) |
| **F7** | Deploy: push → `migrate` → `load_brands`/`seed_category_codes` → **`guard_catalog`** | `guard_catalog` confirma que o catálogo não despencou |

**Suíte inteira antes de qualquer push:**
`python manage.py test chips estoque pricing vendas --settings=core.settings_test`

### Ordem que NÃO funciona
F6 antes de F1–F4: um `known_part` com `chip_type="SoC"` aprovado **antes** de existir caixa
e preço cai no gateway como INDETERMINADO âmbar, e o operador vê um chip sem destino. O
handshake existe justamente para impedir isso — respeite a ordem.

---

## 10. Decisões que dependem de você (e do Wu Quan)

1. **Modelo de preço: A (¥ fixo/unidade) ou B (3G/4G)?** §8.
   *Recomendo A.* Trocar depois só é barato **antes** de existir caixa física.
2. ~~**Área do comprador: Opção I (admin) ou II (grid)?**~~ ✅ **RESPONDIDO 2026-08-17:**
   SSD e K9 entram no painel (trabalho separado); SoC fica **admin-first**. Ver §7.
   ⏳ **Resta decidir a UI** do trabalho A: bloco "Taxas" separado do grid de faixas? (§7)
3. **Uma caixa `I-01` ou uma por geração?** Decorre de 1, mas é decisão física da bancada —
   quantas caixas a mesa comporta.
4. **O `SoC` fica RENTÁVEL sempre, ou tem critério?** O branch da F2 precisa de uma regra.
   Opções: sempre RENTÁVEL (como o K9); ou RENTÁVEL só com `known_part` confirmado
   (protege contra SoC não identificado virar caixa). *Recomendo a segunda* — dado que a
   marca não tem gramática, o registro confirmado é a única garantia de identidade.
5. **Alias `"cpu"` entra?** *Recomendo sim* — é o termo que o operador e o comprador usam.
   `"ap"` eu deixaria de fora (2 letras, casa lixo).
6. 🔴 **PMIC e RF seguem catálogo?** Este plano é **só** `SoC` — mas o comprador exige **套片**
   (conjuntos casados, `SPREADTRUM.md §4.9`). Se ele confirmar que compra conjuntos, o escopo
   real vira **três tipos comerciais** (SoC + PMIC + RF), três letras, três caixas. **Não decidir
   antes da resposta dele** à pergunta desambiguadora (§8.5.3).
7. **`Brand` = "Spreadtrum" ou "UNISOC"?** §8.5.4 — *recomendo uma só: Spreadtrum*.

---

## 11. Rollback

Tudo é **aditivo** — nenhum dado existente muda de sentido (blast radius zero, §1).

| Camada | Como desfazer |
|---|---|
| `chip_types.py` | reverter a entrada para `commercial=False, "none", "indeterminado"` |
| `engine` / `estoque` / `pricing` | reverter o commit; branches novos são isolados por `kind` |
| Migração `0024` | `AddField` nullable → reverter é `RemoveField`; nenhum dado perdido |
| `FOUNDING_TABLE` / `CategoryCode` | ⚠️ **a linha `('soc','','1','',1)` é APPEND-ONLY e ETERNA** (`convention.py:37`). Não se apaga categoria. Se o negócio recuar, a `I-01` fica órfã e sem preço — é o desenho, não um bug |
| `known_parts` aprovados | não rebaixar; `restore_known_parts` se precisar |

**O único ponto irreversível é a letra `I` e o código `I-01`.** Por isso a decisão nº 3
(§10) tem que sair **antes** da F4.

---

## 12. Checklist de handoff (para quando a implementação for autorizada)

- [ ] Decisões §10 respondidas pelo dono
- [ ] `SoC` mantém `category="catalog"` (§3) — verificado no diff
- [ ] `tests_convention.py:159` invertido + `"soc"` nos vocabulários fechados
- [ ] Branch de rentabilidade criado → `RentabilidadeHandshakeTests` verde
- [ ] `characterize_baseline --diff` = **0** (aditivo puro)
- [ ] `seed_category_codes` rodado; `I-01` existe e é idempotente
- [ ] `check_translations` exit 0 nos 4 idiomas; código de caixa **não** traduzido
- [ ] Suíte inteira verde (`chips estoque pricing vendas`)
- [ ] `Buyer.soc_rmb_each` **vazio** até o OK do Wu Quan (padrão K9: sem preço **com motivo**,
      nunca chutar)
- [ ] `guard_catalog` verde pós-deploy

---

## 13. Referências

- `SPREADTRUM.md` — a marca, a ausência de gramática, a realidade de mercado
- `AUTORIA.md` — duas trilhas, portão, golden, handshake, four-eyes
- `PRECIFICACAO.md §12.22` — a decisão do K9 (tipo plano ¥ fixo/unidade)
- `CLAUDE.md §5, §6` — contrato e convenção
- `chips/chip_types.py` · `chips/engine.py::assess_profitability` ·
  `estoque/views.py::_compute_destination` · `pricing/{models,convention,engine,views,admin}.py`
- Precedente de migração: `pricing/migrations/0023_buyer_k9_rate.py`
