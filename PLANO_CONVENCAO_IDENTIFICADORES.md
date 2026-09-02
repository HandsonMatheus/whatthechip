# Plano de execução — convenção de identificadores (LOT / SO)

> Contrato: `CONVENCAO_IDENTIFICADORES.md` (a decisão). Este arquivo é o **como**,
> com as decisões complementares que o dono tomou em **2026-09-02** e a ordem em
> que a coisa entra. Ambos somem quando a implementação estiver no ar (§11).
>
> **STATUS 02/09 — LOCALHOST ENTREGUE.** Suíte inteira verde (1314 testes; a
> única vermelha é `GoldenObrigatorioTests`, das famílias MEMA/MEMD do
> `isocom.yaml`, de outro chat). Migrações `tenancy/0013`, `estoque/0023`,
> `vendas/0021` e `vendas/0022` aplicadas; catálogos i18n publicáveis; backfill
> commitado (2 empresas, 30 documentos) e idempotente na 2ª passada; contador
> de lote da eMiner corrigido de 50 para 13. **Falta produção.**
>
> **PRÉ-VOO DE PRODUÇÃO (02/09, só leitura).** O banco da Render é espelho do
> local: mesmas 2 empresas sem código, eMiner com lotes 1–13 (a renumeração de
> 01/09 chegou lá), eRecyclo 1–4, tudo de 2026, mesmas ordens 1–11 e 1–2, e o
> MESMO contador adiantado (`last_lot_number=50`). Contadores reais:
> `so`=11 e `inv`=7 na eMiner, `so`=2 na eRecyclo — todos iguais ao maior
> número existente, então **não há ordem apagada** e o piso do §4 não muda
> nada. A semeadura da `0022` deve dar lot=13/4, so=11/2, inv intocada.
> Única diferença: produção tem 7 faturas, o local 8.

---

## 0. Decisões travadas em 2026-09-02

| # | Pergunta | Decisão |
|---|---|---|
| D1 | A fatura (INV) entra na convenção? | **NÃO. Não tocar na INV.** Ela é aposentada hoje à noite, em entrega separada. O `code_str` da INV continua saindo `INV/EMI/003/08/26`. |
| D2 | Prefixo da eMiner | **`EMIN`** — muda de `EMI` para 4 letras. |
| D3 | E as outras empresas? | **Todas para 4 letras.** eRecyclo `ERC` → `EREC`; as três de demo/teste re-semeadas. |
| D4 | O reinício anual vale para o lote? | **Sim — lote e OV reiniciam.** O contador do lote sai do `Company.last_lot_number` e passa para o `DocSequence`, por ano. |
| D5 | Alcance do backfill | **Todo lote e toda SO, de todas as empresas**, inclusive documento já despachado, faturado e quitado. Só a grafia muda; número, data e valor não. |
| D6 | Busca por grafia antiga | **Só a grafia nova.** Ver o desvio abaixo. |
| D7 | Lote apagado devolve o número? | **Sim — mas só o ÚLTIMO e só se estava ABERTO.** Abrir → apagar → abrir dá o MESMO número. Lote que chegou a fechar (já gerou PDF com o código) não devolve; buraco no meio continua buraco. ⚠ Contraria o §4 do contrato ("número emitido nunca se reusa") — ver §0.2. |
| D8 | Vale para a OV? | **Não, só o lote por enquanto.** Rascunho de OV apagado não recua a sequência. |
| D9 | Buracos que já existem | **Deixa como está.** A correção vale daqui pra frente; buraco antigo some sozinho na virada do ano, quando tudo reinicia em `0001`. Nada de recontar outras empresas nesta entrega. |
| D10 | Aviso no modal de excluir | **Sim, uma linha**, e só quando a devolução vai mesmo acontecer (último + nunca fechado). 1 string nova nos 4 idiomas. |
| D11 | Semente do contador de lote | **O maior número REAL do ano** (eMiner: 13 → próximo lote é o 14), não o `last_lot_number` atual (50). Ver §0.3. |

### ⚠ D6 é um desvio consciente da §6.5 do contrato

A spec chama a busca pelas duas grafias de *"obrigatório, não opcional"* e diz que
sem ela *"esta mudança destrói rastreabilidade"*. A decisão de hoje derruba isso.
O que sobra de rede, e que é real:

- A busca é **substring** sobre um haystack. Quem tem `LOT/003/05/26` no papel e
  digita **`003`** continua achando o lote (`LOT-2026-0003` contém `003`).
- O que deixa de funcionar é colar a **string inteira antiga**.
- ⚠ E há um agravante que não está na spec: a renumeração de ontem
  (`renumerar_lotes_eminer`, 2026-09-01) já trocou os **números** — o papel do
  Wu Quan pode dizer `LOT/039/05/26`, cujo `039` **não existe mais em lugar
  nenhum**. Nem a busca pelas duas grafias resolveria esse caso; só um alias
  histórico gravado resolveria.

Custo de voltar atrás depois: **duas linhas** no `purchase_haystack` (reconstruir
`LOT/{n:03d}/{mm}/{yy}` e a versão com prefixo). Fica registrado aqui para não
virar descoberta arqueológica.

### ⚠ D7 é um desvio consciente do §4 do contrato

O contrato diz **"número emitido nunca se reusa"**, pela mesma razão dos códigos de
caixa (F12). O dono pediu o reuso em 2026-09-02, e o **alcance escolhido é o que
preserva o espírito da regra**: só volta o número que nunca chegou a virar
documento. Lote fechado emite PDF de conferência com o código dentro; esse número
fica queimado para sempre, como antes. O que volta é o número de um lote que foi
aberto e apagado sem nada ter saído dele — que não é "reusar um número emitido",
é desfazer uma abertura.

⚠ Não vale para buraco no meio: apagar o 48 com 49 e 50 vivos deixa o 48 vago
para sempre. Fechar buracos é `renumerar_lotes_eminer`, comando à parte, com
revert — nunca comportamento automático da tela.

---

## 0.3 O que o retrato do banco (02/09) mudou no plano

`python retrato_numeracao.py` (script READ-ONLY na raiz) contra o localhost:

- **As duas empresas estão com `Company.code` VAZIO.** `EMI`/`ERC` só existiam nos
  testes — o backfill de 18/08 foi revertido. Então `EMIN`/`EREC` **não são troca
  de prefixo em uso, são o prefixo nascendo**: o aviso do §6.3 do contrato
  (NetSuite) não se aplica, e o risco de renomear documento antigo cai muito.
- **Nenhum documento fora de 2026**, em nenhuma das duas. A frase do contrato
  ("aplicar o reinício agora não renumera nada") se confirma.
- **Nenhum buraco** na numeração de nenhuma das duas (D9 fica sem efeito prático).
- **6 ordens da eMiner e 2 lotes da eRecyclo estão com `code_str` VAZIO** — hoje
  eles caem no formato calculado. O backfill grava a grafia nova neles também.
- ⚠ **`eMiner.last_lot_number = 50`, mas o maior lote é o 13.** A renumeração de
  01/09 comprimiu 39–50 em 1–13 e **não recuou o contador**; a auto-cura do
  `open_for_company` só empurra para cima. Hoje, abrir um lote daria **#51**, com
  um buraco de 14 a 50. **D11:** a migração semeia `DocSequence['lot', 2026]` com
  o `Max(number)` REAL de cada (empresa, ano) — 13 na eMiner, 4 na eRecyclo — e
  alinha o `last_lot_number` ao mesmo valor, para o admin não exibir uma mentira.
  ⚠ Lição aplicada: o `renumerar_lotes_eminer` agora **acerta o contador** ao
  renumerar (`_acertar_contador`), com teste próprio. A auto-cura do
  `open_for_company` só empurra o contador para CIMA — contador ADIANTADO ela
  não enxerga, e foi por isso que o problema sobreviveu à recontagem.

---

## 0.4 O que a execução (02/09) ensinou

- **Um `ValueError` de uma linha derrubou 255 testes.** `next_for_lot` passava
  `lot.company_id` (int) onde o `get_or_create` exige a instância. O erro
  estourava DENTRO do `try` largo de `create_draft_for_lot`, que **engole a
  exceção e devolve `None`** — então a maioria das quebras aparecia como
  "unexpectedly None" e listas vazias, longe da causa. É a mesma classe do bug
  do K9 (agosto). O `next_number` agora aceita instância **ou** pk; o `except`
  largo continua sendo a razão de o diagnóstico custar caro.
- **O portão de i18n pega mudança de mensagem, não só string nova.** Alterar o
  exemplo do validador (`"EMI"` → `"EMIN"`) mudou o `msgid` e derrubou os três
  catálogos. Entraram: `Origem` (cabeçalho novo), o aviso de devolução de
  número (D10) e o `msgid` alterado — mais `compilemessages`, sem o qual o
  `.po` editado não vale.
- **Migração de dados em app próprio, não editando a gerada.** As constraints
  novas não violam com `doc_year=0` (a chave antiga já era única), então a
  `0022` roda DEPOIS da `0021`/`0023` sem precisar entrar no meio delas.
- **A suíte inteira, não três apps.** `chips` e `pricing` hospedam o portão de
  i18n; rodar só `tenancy estoque vendas` deu verde com o catálogo quebrado.

---

## 1. Ordem do dia

```
localhost  →  suíte verde  →  réplica (opcional)  →  PRODUÇÃO (convenção)
                                                          ↓
                                                   deploy separado
                                                          ↓
                                                   PRODUÇÃO (aposentar INV)
```

**A convenção vai ANTES da INV** (§9 do contrato) e em **deploy separado**: quando
algo quebrar hoje à noite, tem de dar para saber qual das duas mudanças causou.

⚠ **Conflito de migração entre as duas entregas.** As duas mexem em
`vendas/migrations/`. Se a aposentadoria da INV for escrita em paralelo por outro
chat, uma das duas vai encontrar `0021` ocupado. Quem for **segundo** rebasa a
própria migração em cima da primeira — nunca renumerar a que já foi aplicada.

---

## 2. Fase A — a grafia (fonte única)

**A1. `tenancy/doc_code.py` — vira mapa por tipo, não `if`** (§7 do contrato)

```python
FORMATOS = {
    'LOT': lambda cod, n, ano: f'LOT-{ano}-{n:04d}',                    # sem prefixo (§2.5)
    'SO':  lambda cod, n, ano: f'{cod}-SO-{ano}-{n:04d}' if cod else f'SO-{ano}-{n:04d}',
    'INV': _legado,                                                     # ⚠ D1 — intocada
}

def doc_code(prefixo, company_code, number, quando=None, *, ano=None) -> str
```

- Assinatura **posicional preservada** — a `Invoice.save()` chama
  `doc_code('INV', code, number, timezone.now())` e não pode quebrar (D1).
- `ano` explícito é o caminho da SO (herda do lote, §2.2). Ausente, deriva de
  `timezone.localtime(quando).year`.
- ⚠ **`localtime`, não `now()`.** Hoje o código formata `%m/%y` sobre UTC: um lote
  aberto 31/dez 21:00 em Assunção (UTC−3) já é 1º/jan em UTC e sairia com **o ano
  errado** — exatamente a fronteira que esta convenção existe para acertar. Bug
  latente hoje (erra o mês), fatal depois (erra o ano).

**A2. `tenancy/models.py` — semente de 4 letras**

- `suggest_company_code`: `letras[:3]` → `letras[:4]`, com o mesmo desempate
  (4 → 5? não: 4 letras → 3 letras + B, C, D…, mantendo `max_length=4`).
- `validate_company_code` **continua aceitando 2 a 4 letras**: vazio é o legado
  (§3) e não se fecha a porta para um código curto escolhido à mão.
- A troca dos códigos das empresas **existentes** (D2/D3) **não** é feita aqui —
  é passo do backfill (Fase C), onde é reversível.

---

## 3. Fase B — contadores e chave de unicidade

**B1. `DocSequence` ganha o ano**

- `+ year = PositiveSmallIntegerField(default=0)`; `+ SEQ_LOT = 'lot'`.
- `unique (company, kind)` → **`unique (company, kind, year)`**.
- `next_number(company, kind, year=0)` — mantém `select_for_update`.
  `year=0` = sequência **perpétua**, e é o que a INV continua usando (D1) sem
  saber que algo mudou.
- ⚠ O `year=0` como default existe por um motivo mundano: `next_number(emp, SEQ_SO)`
  aparece em ~20 arquivos de teste. O **caminho real** nunca usa o default — e há
  trava provando (§7).

**B2. `Lot` — ano congelado e número por ano**

- `+ doc_year = PositiveSmallIntegerField` (ano de ABERTURA, §2.1). Campo
  **gravado**, não derivado: é ele que entra na chave de unicidade, e derivar de
  `created_at` num índice funcional traz o fuso junto.
- `unique (company, number)` → **`unique (company, doc_year, number)`**.
- `open_for_company`: `ano = timezone.localdate().year`;
  `number = DocSequence.next_number(company, SEQ_LOT, ano)`.
  A trava de corrida continua existindo — muda de linha (`Company` → `DocSequence`),
  não de natureza. Mantém a auto-cura: `max(contador, Max(number) DAQUELE ano)`.
- `Company.last_lot_number` **fica no lugar** (o `bootstrap_tenancy` e o admin o
  leem) mas deixa de ser fonte. Remover é limpeza para outro dia — não hoje.

**B3. `SalesOrder` — herda o ano do lote**

- `+ doc_year`; `unique (company, number)` → **`unique (company, doc_year, number)`**.
- `save()`: `doc_year = lot.doc_year`, e o código sai com `ano=self.doc_year`.
- `+ SalesOrder.next_for_lot(lot) -> (doc_year, number)` — **um** lugar que sabe
  puxar do contador do ano certo. Chamadores reais que passam a usar:
  `vendas/services.py:75` (fechamento do lote), `backfill_sales_orders.py:97`,
  `criar_lotes_legados_eminer.py:184`, `demo_repasse_automatico.py:338`.

**B4. Migrações** — `estoque/00XX` e `vendas/00XX`, cada uma em **três atos na
mesma transação**: `AddField` (nulo/0) → `RunPython` (preenche) → swap da
constraint.

⚠ **RLS.** O `RunPython` roda no build da Render **sem GUC e sem superuser**: com
`FORCE RLS` a policy devolve **zero linhas em silêncio** e o backfill "passa"
sem tocar em nada. Copiar o padrão já provado do
`vendas/migrations/0013_backfill_invoice_fee.py`:

```python
def _liberar_rls(schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL app.platform = '1'")
```

Preenchimento: `Lot.doc_year` = ano de `created_at` **em horário local**;
`SalesOrder.doc_year` = o `doc_year` do lote dela; `DocSequence.year = 2026` nas
linhas `so` existentes (`inv` fica em `0`, perpétua); cria a linha `lot` de cada
(empresa, 2026) com `last_number = Max(number)` dos lotes daquele ano.

**B5. Devolver o número quando o lote é apagado** (D7)

Hoje: `estoque/views.py::lot_delete` chama `lot.delete()` e ninguém toca no
contador; a abertura seguinte faz `max(contador, Max(number))+1` e o número
apagado fica queimado. É o bug relatado.

- `Lot.delete()` sobrescrito (**portão no MODELO**, não na view: admin, shell e
  comando passam pelo mesmo caminho). Dentro de `transaction.atomic()`.
- Devolve o número **só se as duas forem verdade**:
  1. é o **maior número** da (empresa, ano) — na prática, `seq.last_number == self.number`;
  2. o lote **nunca foi fechado** — `closed_at is None` **e** sem evento de
     fechamento no pghistory (`LotEvent` com `status='closed'`). ⚠ O `closed_at`
     sozinho não basta: reabrir zera o campo, e um lote reaberto já emitiu PDF.
- `DocSequence.release_number(company, kind, year, numero)`: `select_for_update`
  na MESMA linha que a abertura trava — apagar e abrir simultâneos serializam. Se
  o contador já andou (`last_number != numero`), **não faz nada** e não é erro.
- A auto-cura do `open_for_company` (`max(contador, Max(number) do ano)`) continua
  sendo a rede: mesmo que a devolução falhe, nenhum número duplica.
- ⚠ `queryset.delete()` em massa **não** passa por aqui — de propósito: os
  comandos de renumeração/limpeza não podem mexer em contador por efeito colateral.
- **Modal de exclusão** (D10): quando (e só quando) a devolução vai acontecer, o
  modal ganha uma linha dizendo que o número volta a ficar disponível. A view já
  sabe decidir isso — o mesmo predicado do `Lot.delete()`, exposto como propriedade
  (`Lot.devolve_numero_ao_excluir`) para o template não repetir a regra.
  ⚠ String nova nasce com `{% trans %}` e vai para os 4 `.po` (CLAUDE.md §6).

---

## 4. Fase C — o passado (`backfill_doc_codes`)

O comando **já existe**, já é `SafeWriteCommand` (mostra o banco-alvo, exige
digitar o nome no `--commit`), já abre `company_scope` por empresa e já grava
`backfill_doc_codes_revert.json`. O que muda:

1. **`ALVOS` perde a `Fatura`** (D1). Sobram Lote e OV.
2. **Passo novo: re-semear o código das empresas para 4 letras** (D2/D3) —
   `EMI`→`EMIN`, `ERC`→`EREC`, e as demo. Colisão resolve pela regra existente. O
   valor anterior entra no revert.
3. `tem_codigo_de_empresa()` (que faz `split('/')`) vira **`ja_no_formato_novo()`**
   — a pergunta agora é outra: o `code_str` já está na grafia nova?
4. Reescreve `code_str` de **todo** lote e **toda** SO com o formato novo
   (`doc_code` + o `doc_year` da Fase B). **Idempotente**: a segunda rodada
   calcula o mesmo valor e não escreve nada.

⚠ **Ordem obrigatória:** re-semear os códigos **antes** de reescrever os
documentos, senão as SO saem com `EMI` e o passo 2 não as alcança mais.

---

## 5. Fase D — painel do comprador (§5 do contrato)

`vendas/templates/vendas/partner_compras.html`:

- A coluna **Lote sai** da tabela.
- **Ordem** vira a primeira coluna.
- **Origem ganha coluna própria** (decisão de hoje) — o selo hoje mora colado no
  código do lote e iria embora junto. Herda `hide-lg`? **Não**: o selo é leitura
  de varredura; quem cede largura abaixo de 1100px continua sendo Chips e Total US$.
- `vendas/services.py` — `_PURCHASE_KEY['so']`: `(s.number, s.pk)` →
  **`(s.doc_year, s.number, s.pk)`**. Sem isso, na virada do ano a ordenação por
  "Ordem" mistura 2026 e 2027 (o `0001` de 2027 vem antes do `0041` de 2026).
- `purchase_haystack` **mantém `so.lot.code`** — é o que preserva o lote buscável
  fora da tabela; vira trava de teste explícita.
- O **CSV do comprador mantém a coluna do lote** (`views.compras_csv`): o contrato
  tira o lote da *tabela*, não do dado exportado.
- `partner_compra.html` (detalhe): o lote **continua** no cabeçalho da compra.

---

## 6. Fase E — varredura

| Lugar | O quê |
|---|---|
| `estoque/views.py:1605` | Nome do xlsx: `lote_003_20260902.xlsx` → incluir o ano (`lote_2026_0003_…`). Com reinício anual, dois arquivos de anos diferentes colidiriam na pasta de Downloads. |
| `estoque/models.py` `Lot.__str__` | `Lote #003` fica ambíguo entre anos. Passa a usar o `code`. |
| `vendas/views.py:216` | `'PACKING-LIST-' + so.code.replace('/', '-')` — o `replace` vira no-op (a grafia nova já usa `-`). Nada a fazer; anotado para ninguém "consertar". |
| `estoque/templates/estoque/estoque.html` | Type-to-confirm de fechar/apagar lote usa `lot.code`: passa a exigir `LOT-2026-0003` digitado. Funciona, só é mais longo. Confirmar com o dono se incomoda na bancada. |
| `*_eminer.py` (5 comandos) | Constantes com o código antigo literal (`ORDEM = 'SO/004/08/26'`). São one-offs **já executados**; ficam congelados. ⚠ Um `--revert` deles depois do backfill não acha mais o documento — se precisar, passar o código novo. Os testes deles fazem `patch` da constante, então a suíte não sente. |
| `design_v2/ui_kits/**.html` | Protótipos estáticos com `LOT/042/07/26` de mentira. Sem efeito em produção; atualizar quando o v2 for encostado. |

---

## 7. Travas — nada disto está entregue sem elas

**Suíte (SQLite):**
- [ ] Formato dos dois documentos, com e sem código de empresa.
- [ ] Empresa sem código → `SO-2026-0004` (e nunca `-SO-2026-0004`).
- [ ] Colisão de prefixo recusada no cadastro.
- [ ] SO herda o ano do lote — **com o caso de dezembro→janeiro**.
- [ ] O número reinicia na virada do ano (lote **e** OV).
- [ ] ⚠ O contador de 2026 anda em 2027 quando o lote é de 2026 (§2.4).
- [ ] O lote continua buscável no painel do comprador **fora** da tabela.
- [ ] ⚠ `INV` **não mudou** — trava que fixa a decisão D1 por escrito.
- [ ] O caminho real da SO puxa do contador do **ano do lote** (nunca do `year=0`).
- [ ] `doc_year` do lote sai do **horário local**, não de UTC (caso 31/dez 21:00).
- [ ] Testes existentes que fixam a grafia antiga: `tenancy/tests.py` (14
      ocorrências), `vendas/tests.py` (4), `estoque/tests_descricao_lotes_eminer.py`
      (3), `vendas/tests_ordem_envio.py` (2) e mais 4 com 1 cada.
- [ ] `estoque/tests.py` (auto-cura e corrida do contador de lote) migram do
      `last_lot_number` para o `DocSequence`.
- [ ] **D7:** abrir → apagar → abrir devolve o **mesmo** número.
- [ ] **D7:** apagar um lote que **não é o último** deixa o buraco (o próximo
      continua sendo o seguinte ao maior).
- [ ] **D7:** lote que foi **fechado** (mesmo reaberto depois) **não** devolve.
- [ ] **D7:** a devolução não atravessa empresa nem ano.
- [ ] **D10:** o aviso do modal aparece no lote que devolve e **some** no que não
      devolve (fechado, ou não é o último).

**Mutação — cada uma tem de MORDER:**
- [ ] Prefixo derivado do nome em vez do `Company.code`.
- [ ] SO usando o próprio ano em vez do ano do lote.
- [ ] Número não reiniciando na virada do ano.
- [ ] Prefixo de empresa no lote.
- [ ] `doc_year` a partir de UTC em vez de local.
- [ ] Lote fora do haystack do comprador.
- [ ] Devolver o número sem checar se o lote era o último (D7).
- [ ] Devolver o número de um lote que já foi fechado (D7).

**Réplica (Postgres, papel restrito — RLS real):**
- [ ] Backfill **idempotente**: segunda rodada não altera nada.
- [ ] As duas constraints novas aplicam sem violação nos dados reais.
- [ ] O `RunPython` das migrações escreve **mesmo** sob RLS (o que o `SET LOCAL
      app.platform` garante) — conferir contagem, não confiar no "ok" da saída.

---

## 8. Runbook — localhost

```bash
# 0. retrato do antes (guardar a saída — é o diff de aceite)
python manage.py diag_ordem_venda            # ou o dump de códigos/contadores
python manage.py backfill_doc_codes          # dry-run: mostra empresa por empresa

# 1. código (Fases A, B, D, E) + migrações
python manage.py makemigrations estoque vendas tenancy
python manage.py migrate            # inclui a 0022 (dados + contadores)

# 2. i18n — string nova/alterada quebra o portão, e o .po só vale compilado
python manage.py compilemessages
python manage.py check_translations

# 3. suíte INTEIRA (o portão de i18n mora em chips/pricing)
python manage.py test --settings=core.settings_test        # (§5 do CLAUDE.md)

# 4. o passado
python manage.py backfill_doc_codes                        # dry-run, lê com calma
python manage.py backfill_doc_codes --commit
python manage.py backfill_doc_codes                        # 2ª vez: "Nada a fazer."

# 5. olho na tela
#    painel do comprador (ordem 1ª, origem em coluna, sem lote)
#    busca por "0003" e por "EMIN"
#    fechar um lote de mentira: type-to-confirm com LOT-2026-00NN
#    abrir um lote novo: número segue a sequência de 2026
```

Rollback local: `python manage.py backfill_doc_codes --revert` e `migrate` para trás.

## 9. Runbook — produção (hoje à noite)

1. **Backup** do banco antes de qualquer coisa.
2. Deploy do código + `migrate` (o `RunPython` preenche `doc_year` e semeia o
   `DocSequence`).
3. `backfill_doc_codes` **dry-run** — ler a lista inteira; é aqui que se vê
   `EMI → EMIN` e `ERC → EREC` antes de acontecer.
4. `backfill_doc_codes --commit` (o `SafeWriteCommand` vai exigir digitar o nome
   do banco — confira que diz **produção**).
5. Rodar de novo em dry-run: tem de dizer **"Nada a fazer"**.
6. Conferência na tela: painel do comprador, uma OV antiga, um lote antigo.
7. **Só então** o deploy da aposentadoria da INV.

⚠ Guardar o `backfill_doc_codes_revert.json` de produção. Ele é o caminho de volta
dos códigos das empresas e de todo `code_str` reescrito.

---

## 10. Riscos assumidos

1. **A grafia antiga fica órfã na busca** (D6, §0). Mitigação parcial: buscar pelo
   número solto ainda casa.
2. ~~Mudar `EMI` → `EMIN` com numeração em uso~~ — **caiu**: o retrato mostrou os
   códigos VAZIOS, então o prefixo está nascendo, não mudando (§0.3).
3. **Duas entregas na mesma noite.** Separar os deploys e conferir entre eles é o
   que mantém o diagnóstico possível.
4. **Documento impresso diverge da tela.** Já era verdade desde 18/08 e desde a
   renumeração de ontem; esta entrega aumenta a distância.

---

## 11. Encerramento documental

Quando estiver no ar e conferido:

- [ ] `CLAUDE.md §6` recebe a convenção (a forma, o ano do lote, a herança da SO,
      o reinício anual).
- [ ] `CLAUDE.md §7` recebe as armadilhas: o contador que anda depois do ano
      acabar (§2.4), o `localtime` no ano do documento, e o `SET LOCAL
      app.platform` em `RunPython` sobre tabela com RLS.
- [ ] `CONVENCAO_IDENTIFICADORES.md` e este plano **somem** — são a ponte entre a
      decisão e o código, não bíblia.
