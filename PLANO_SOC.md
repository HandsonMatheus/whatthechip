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
| 3 | 🟡 **`SSD` e `K9` NÃO aparecem na área do comprador.** `_NAV_KINDS` (`pricing/views.py:121`) só tem emcp/umcp/lpddr/emmc/ufs/ddr. | Se SoC copiar o K9, o Wu Quan **não** consegue cotar sozinho — o preço entra pelo admin. Isso contraria seu pedido literal e vira **decisão explícita** (§7). |

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

## 7. 🟡 A área do comprador — o achado que contraria o pedido

Você pediu "também na área do comprador para ser cotado". O código diz o seguinte:

```python
# pricing/views.py:121
_NAV_KINDS = ('emcp', 'umcp', 'lpddr', 'emmc', 'ufs', 'ddr')
```

**`ssd` e `k9` não estão lá.** Não é esquecimento — é a arquitetura: os dois têm preço
**fórmula**, não **grid**. O ¥ mora no registro `Buyer` (`ssd_rmb_per_gb`, `k9_rmb_each`) e é
editado no **admin do Django**, pelo dono. O comprador não tem tela para eles.

Isso cria uma bifurcação real:

### Opção I — SoC segue o padrão K9/SSD (preço no `Buyer`, admin)
- ✅ Copia um caminho já provado em produção; **~1 dia** de trabalho
- ✅ Migração trivial (`AddField`), zero risco de RLS
- ❌ **O Wu Quan não cota sozinho** — você vira o intermediário: ele manda o ¥, você digita
- ❌ Contraria a leitura literal do seu pedido

### Opção II — SoC como kind de GRID (aparece na área do comprador)
- ✅ O comprador edita o preço sozinho, como faz com eMMC/DDR
- ✅ Cria naturalmente o caminho para diferenciar 3G × 4G (uma linha cada)
- ❌ Mais trabalho: `_NAV_KINDS` + `partner_kind` + `partner_kind_save`
- ❌ 🔴 **`pricing/views.py:514` valida `tier_unit in ('GB','Gb')`** — um tipo sem unidade
  **não passa** no save do parceiro. Precisa ser relaxado, e isso mexe num caminho que
  serve **todos** os kinds. É o único ponto do plano que toca código compartilhado
- ❌ Precisa de tradução das novas telas (4 idiomas)

> **Minha recomendação: I agora, II depois — e só se o comprador pedir.**
> Motivo: enquanto **não existe preço de referência público** para SoC recuperado
> (`SPREADTRUM.md §6`), o primeiro ¥ vai sair de uma conversa com o Wu Quan, não de uma
> tela. Construir a tela antes de existir o número é construir para uma demanda hipotética.
> A Opção II fica documentada e barata de fazer depois — nada da Opção I precisa ser
> desfeito.

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
2. **Área do comprador: Opção I (admin) ou II (grid)?** §7.
   *Recomendo I.* Nota: hoje nem SSD nem K9 estão no self-service do comprador.
3. **Uma caixa `I-01` ou uma por geração?** Decorre de 1, mas é decisão física da bancada —
   quantas caixas a mesa comporta.
4. **O `SoC` fica RENTÁVEL sempre, ou tem critério?** O branch da F2 precisa de uma regra.
   Opções: sempre RENTÁVEL (como o K9); ou RENTÁVEL só com `known_part` confirmado
   (protege contra SoC não identificado virar caixa). *Recomendo a segunda* — dado que a
   marca não tem gramática, o registro confirmado é a única garantia de identidade.
5. **Alias `"cpu"` entra?** *Recomendo sim* — é o termo que o operador e o comprador usam.
   `"ap"` eu deixaria de fora (2 letras, casa lixo).
6. **PMIC e Sensor seguem catálogo?** Este plano é **só** `SoC`. Se o lote trouxer `SC27xx`
   (PMIC) e `SR3xxx` (RF), eles continuam sem caixa — decisão separada, mesmo molde.

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
