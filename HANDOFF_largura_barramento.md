# HANDOFF — Levantamento de LARGURA DE BARRAMENTO por marca

Você assume um trabalho que já foi feito **inteiro** para uma marca (Samsung) e
precisa ser repetido para as outras. Este documento não é um resumo: é o método,
com os erros que já custaram tempo marcados no lugar onde eles acontecem.

Leia até o fim antes de rodar qualquer coisa. O trabalho tem uma armadilha
central que destrói o resultado **em silêncio**, e ela está na seção 3.

---

## 1. O que estamos construindo e por quê

O sistema precisa distinguir chips de DRAM de **4 e 8 bits** dos de **16 bits**
(largura do barramento de dados, o "xN" do datasheet). Uma feature será montada
em cima disso.

O produto final, por marca, é uma planilha/CSV com os PNs de **x4 e x8** em que
existe **prova** — não palpite, não padrão, não "provavelmente". O dono foi
explícito: só entra o que tem certeza.

### Fora de escopo, decidido pelo dono

- **GDDR é sucata.** Não entra em lote nenhum, não vale dinheiro. Não gaste um
  minuto com família GDDR, nem para "completude do catálogo".
- **x16 e x32** não vão para a planilha. Podem (e devem) ser medidos, porque
  servem de contraprova da regra — mas o entregável é 4 e 8 bits.
- **LPDDR, eMMC, eMCP, uMCP, UFS, NAND**: outra gramática de PN. Fora.

---

## 2. O contrato de operação — não se negocia

Estas regras vêm do dono e valem para tudo:

1. **TRAVA DE ESCRITA.** Agente nunca escreve no catálogo direto (shell, ORM,
   admin). O caminho é `chips/knowledge/<marca>.yaml` → `load_brands --brand
   <marca> --commit`. Sempre.
2. **Quem roda comando que grava é o dono.** Você prepara, explica e entrega com
   dry-run. Não peça para ele rodar `--commit` sem ter mostrado o dry-run antes.
3. **Nada vai para produção sem passar pelo local.** O script imprime o
   banco-alvo na primeira linha: `env -u DATABASE_URL python ...` usa o Postgres
   local; com `DATABASE_URL` exportado vai no Render. **Confira a linha do
   banco-alvo toda vez** — já aconteceu de rodar em produção achando que era
   local.
4. **Verificar antes de afirmar.** Se não tem certeza, diga que não tem. O dono
   prefere "não sei" a um número bonito e errado.
5. **Português do Brasil** ("você"/"pode", nunca "tu"/"podes").
6. Toda leitura de banco é **read-only, em transação revertida**, com **zero
   alto**: ler 0 linhas nunca é "está tudo certo" — é leitura que não aconteceu
   (RLS sem GUC, marca escrita diferente, banco vazio). Aborte vermelho.

---

## 3. ⚠ A ARMADILHA CENTRAL — circularidade

**Leia isto duas vezes.** É o único jeito de este trabalho dar errado sem
ninguém perceber.

O método tem duas leituras independentes da mesma verdade:

- **A REGRA** — a largura deduzida da posição no part number.
- **O BANCO** — o campo **`bus_width`** do `KnownPart` (era `interface` até
  2026-09; a separação está no PLANO_BUS_WIDTH.md), preenchido a partir de
  datasheet / página oficial / distribuidor Tier-1.

O cruzamento das duas é o que autoriza confiar na regra. Se ela concorda com uma
fonte independente 100 vezes sem um único contraexemplo, ela está provada.

**Se alguém preencher o `bus_width` decodificando o PN, o cruzamento vira a
regra concordando com ela mesma.** Os acordos sobem, a família é promovida, a
planilha ganha linhas — e nada foi provado. Isso é o pior resultado possível:
errado com aparência de verificado.

Por isso, duas obrigações suas:

- **Nunca** preencha `bus_width` a partir do PN, e deixe isso explícito em todo
  prompt que você mandar para chat de marca.
- ⚠ **A exceção que virou regra em 2026-09-20, e a armadilha que ela abriu.** O
  dono autorizou tratar o **decodificador oficial de part number publicado pela
  marca** como Tier-1 (é documento do fabricante, igual a um datasheet — só que
  cobre a família inteira). Foi assim que 168 Samsung DDR ganharam largura. **Mas
  esses registros deixam de ser prova independente**: a partir daí o catálogo
  Samsung DDR concorda com a regra porque a regra o escreveu. O
  `COLETAR_largura_bits.py` lê `submissions/*largura_decodificador*.yaml` e
  EXCLUI aqueles PNs da contagem — visível na saída, como "N PN(s) com largura
  vinda do DECODIFICADOR não contam como prova". Se você repetir esse caminho em
  outra marca, o arquivo de submissão TEM de seguir esse padrão de nome, senão a
  exclusão não acontece e a próxima medição mente.
- **Confira a procedência.** Antes de aceitar um acordo como prova, abra as
  `notes` / `source_url` de alguns PNs e veja se citam fonte real. Na Samsung as
  notes diziam *"Samsung Semiconductor Global (Tier 1) ✓"* — foi isso que
  autorizou usar os 100 acordos. Se as notes disserem "derivado do PN", o acordo
  não vale nada.

---

## 4. O método, na ordem

### Etapa 1 — Pesquisar a gramática em FONTE PRIMÁRIA

Ache o *part number decoder* oficial do fabricante, ou um datasheet que declare
a organização. Distribuidor Tier-1 serve; blog e fórum não.

> **Não confie no `.md` interno da marca.** O `SAMSUNG.md` dizia que `46` era
> código de x4. Não é — `46` é bancos+interface do DDR3 e é **idêntico** em x4,
> x8 e x16. Um código que caísse nesse ramo carimbaria "x4" em tudo. O mesmo
> arquivo também classificava K4W como GDDR3, quando a Samsung publica datasheet
> dele como DDR3. Os `.md` são bons, mas são escrita humana e envelhecem:
> **fonte primária manda, e erro achado vira correção no `.md`.**

Anote também os códigos **de canto**: na Samsung existem `06` (x4 empilhado) e
`07` (x8 empilhado), que não estavam em documento interno nenhum. Eletricamente
são 4 e 8 bits, fisicamente são outra coisa — ficam fora do ouro e vão para
REVISAR, com a decisão sobrando para o dono.

### Etapa 2 — Descobrir se a marca já sabe alguma coisa

```
env -u DATABASE_URL python VERIFICAR_largura.py          # a foto completa
```

O campo **`bus_width`** do `KnownPart` guarda a largura (`x4`/`x8`/`x16`/`x32`/
`x64`) ou vazio; o `interface` guarda **protocolo** (`eMMC 5.1`) e nada mais.
⚠ Até 2026-09 era o contrário — a largura morava no `interface`. Se você ler um
script ou doc antigo que diga isso, ele é anterior à separação; ler `interface`
hoje devolve vazio para todo mundo e o resultado é "nenhuma família tem prova",
que **parece** uma medição e não é.

O `VERIFICAR_largura.py` já dá a foto pronta: quanto do catálogo é DRAM, quanto
tem largura por classe, e a **fila de pesquisa só do balde comercial** (DDR/
DDR3L/DDR4/DDR5 — LPDDR e GDDR ficam de fora por decisão do dono).

### Etapa 3 — Rodar o coletor e deixar os DADOS promoverem

Use `COLETAR_largura_bits.py` como base (está na raiz do repo). Ele já faz tudo
que é genérico. **Só uma função é específica de marca:**

```
largura_pela_regra(pn_norm)      ← linha ~83, a gramática da marca
```

Tudo o mais é reaproveitável sem tocar: normalização, cruzamento, trava de
promoção, classificação em OURO/REVISAR/FORA, geração de xlsx+CSV, guardas.

O coletor **recusa marca que não seja Samsung de propósito** (sai com código 2):
`pn[5:7]` é gramática da Samsung e aplicá-la na Micron produziria lixo com cara
de dado. Faça uma cópia por marca, troque aquela função, mantenha o resto.

**A trava de promoção — não mexa nela para ganhar linhas.** Uma família só é
PROVADA se tiver, no banco do dono:

| critério | valor | por que existe |
|---|---|---|
| acordos independentes | ≥ 5 | coincidência não sobrevive a 5 |
| divergências | **0** | um contraexemplo derruba a regra, não é ruído |
| larguras distintas | ≥ 2 | 5 acordos todos x16 não provam discriminação nenhuma |

Nenhuma família entra por decisão sua. Família nova se prova sozinha quando os
dados chegam. **Baixar `MIN_PROVAS` ou `MIN_LARGURAS` para a planilha engordar é
exatamente o que este trabalho existe para não fazer.**

### Etapa 4 — Filtrar o PN individualmente

Além da família provada, cada linha do ouro precisa de:

- `review_status == 'approved'`
- `confidence != 'estimated'`

> **Por quê:** um PN "estimado" pode nem existir no mundo real. A largura de um
> PN inventado é ficção decodificada com precisão. Esse filtro é o que separa
> "coletamos PNs" de "coletamos PNs que existem".

### Etapa 5 — Testar a própria ferramenta (mutação)

Antes de acreditar no resultado, quebre algo de propósito e confirme que fica
vermelho. Na Samsung: baixei `MIN_LARGURAS` de 2 para 1 e vi K4W/K4G/K4J/K4Z
serem promovidas — o que provou que **a trava era o que as segurava**, e não um
bug. E o ouro continuou 93, provando que a trava não custava nenhuma linha.

Faça o mesmo na sua marca. Garantia que você não tentou desligar não é garantia.

### Etapa 6 — Medir o RETORNO por família antes de mandar alguém trabalhar

Esta etapa foi a que mais economizou esforço, e é fácil de pular.

Para cada família travada, conte quantos PNs dela viram **x4 ou x8** pela regra.
Na Samsung:

| famílias | PNs travados | viram x4/x8 |
|---|---:|---:|
| K4A, K4R, K4T, K4H | 101 | **55** |
| K4D, K4G, K4J, K4W, K4Z, K4N | 84 | **0** |

Aquelas 84 são GDDR e DDR gráfico — x16 e x32 apenas. Com o `interface`
perfeitamente preenchido, a planilha de 4/8 bits **não ganha uma linha**. Um
chat que atacasse em ordem alfabética queimaria quase metade do esforço em
retorno zero.

**Sempre entregue a lista de trabalho ordenada por retorno real, e diga
explicitamente o que NÃO fazer.**

Cuidado com família pequena: se ela tem 5 PNs no total e a barra pede 5 acordos,
ela só promove com 100% de cobertura. Marque como baixa prioridade e diga por quê.

### Etapa 7 — Despachar para o chat da marca

O chat da marca é quem pesquisa a largura em fonte Tier-1. ⚠ **O canal NÃO é o
yaml**: `known_parts` não vai mais em yaml (Opção 2). A largura de um PN já
aprovado entra por `submit_known_parts <arquivo> --fill-empty` (campo vazio →
preenche, nunca sobrescreve, nunca mexe em status); se já houver OUTRA largura
gravada, é CONFLITO e quem aplica é o `resolve_conflicts --fields bus_width`. O
yaml só recebe largura de **família** (`bus_width:` na família, via
`load_brands`), que é coisa diferente. Use `PROMPT_chat_Samsung_largura_2026-09-12.md` como molde. O
prompt precisa ter, obrigatoriamente:

1. A armadilha da circularidade **no topo**, antes de qualquer outra coisa.
2. "Se não achar fonte, **deixe vazio**. Vazio é honesto; chute não é."
3. A tabela de prioridade por retorno, e as famílias a **pular**.
4. O critério de pronto (≥5 acordos, 0 divergências, ≥2 larguras).
5. PNs concretos sugeridos, que existam no banco — de preferência PN "base", sem
   sufixo de velocidade, que costuma ter datasheet direto.
6. O formato do campo: `bus_width` recebe só `x4`/`x8`/`x16`/`x32`/`x64` — nunca
   geração de RAM, nunca velocidade, e **nunca no `interface`** (o portão recusa).
7. A trava de escrita: yaml → `load_brands`, nunca banco direto.

### Etapa 8 — REVISAR o CSV que volta  ← o seu trabalho principal

Depois do `load_brands --commit`, rode o coletor de novo. Cada marca deve
terminar com um CSV, e **você audita esse CSV outra vez**. Não é formalidade: é
onde a circularidade e o chute seriam pegos.

**Checklist de revisão do CSV — rode inteira:**

- [ ] **Diff contra a corrida anterior.** Toda linha nova precisa de um motivo.
      Linha que apareceu sem família ter sido promovida e sem `interface` novo é
      sinal de que alguém mexeu na trava.
- [ ] **Procedência, por amostragem.** Pegue 5 PNs que viraram acordo novo e leia
      `notes`/`source_url`. Citam datasheet? Ou dizem "derivado do PN"? Se for o
      segundo, **rejeite a família inteira** e devolva para o chat da marca.
- [ ] **Zero `confidence=estimated`** no ouro.
- [ ] **Zero divergência** nas famílias promovidas. Uma divergência que apareceu
      depois significa que a regra tem exceção — investigue, não arredonde.
- [ ] **Família promovida ganhou largura, não só volume?** 10 acordos todos x16
      não promovem. Se promoveu, alguém mexeu na trava.
- [ ] **Conferência externa cega.** Escolha 3 PNs do ouro e verifique a largura
      direto no datasheet, sem olhar o que o banco diz. Os três têm que bater.
- [ ] **`MIN_PROVAS` e `MIN_LARGURAS` continuam 5 e 2?** Confira no arquivo.
- [ ] **Nenhuma família GDDR no ouro.** Se apareceu, a classificação de
      `chip_type` está errada e isso afeta preço e destino, não só esta planilha.
- [ ] **O total fecha?** `ouro + revisar + fora == PNs da marca no banco`.

Quando algo falhar, **volte para o chat da marca com o caso específico**, não com
"revise tudo". O caso específico é o que ensina.

---

## 5. Armadilhas já pagas — não pague de novo

**Regra certa na família errada.** `K4N51163QC` decodifica como x16 pela posição;
o banco (Tier-1) diz x32. A família K4N foi excluída pela trava. Vai acontecer de
novo em outra marca: **é para isso que a trava existe.** Quando acontecer, não
"conserte" o PN — exclua a família e registre o caso.

**Decodificação plausível e falsa.** `K4E4E164EB` é LPDDR3 e a regra devolvia
"x16", porque calha de ter `16` naquela posição. A trava de família impedia de
sujar o ouro — mas o PN caía em REVISAR com o motivo **errado** ("família sem
prova"), o que mandaria alguém caçar datasheet de LPDDR3 para promover uma
família que aquela regra nunca vai poder promover. **Motivo errado custa trabalho
humano mesmo sem sujar o resultado.** A correção foi testar `chip_type` antes de
aceitar a decodificação (função `e_dram_discreta`, linha ~90) — e o teste sai do
banco, não de uma lista de prefixos, para marca nova entrar certa sozinha.

**Fixture presa a um defeito.** Em outro ponto do sistema, um teste usava como
exemplo um dado que existia justamente para ser consertado. Quando consertaram, o
teste caiu. Se você escrever teste, use valor que nunca vai existir no mundo real.

**O `.md` da marca pode estar errado.** Já dito na Etapa 1, repetido aqui porque
é o erro mais caro: ele parece autoridade e não é.

---

## 6. Estado atual

**Samsung — concluída até o teto do catálogo.**

- 964 PNs no banco · **93 no ouro** (34 x4 · 59 x8), todos K4B.
- Dentro das 93: **52 com prova direta** (datasheet daquele PN exato) e **41 por
  regra** (família K4B provada por 100 acordos, 0 divergências, 3 larguras). A
  coluna `PROVA` separa as duas, e a escolha de onde cortar é do dono.
- Conferência cruzada: um levantamento anterior, feito pelo chat da Samsung por
  outro caminho, tinha 53 PNs. **Zero divergência de largura** nos 52 em comum.
  Os 41 a mais são exatamente os PNs em que o catálogo não tinha `interface`.
- Travado: **K4A (61, DDR4), K4R (21, DDR5), K4T (14, DDR2), K4H (5, DDR1)** — a
  regra decodifica, falta corroboração. Prompt já entregue ao chat da Samsung;
  vale +55 linhas com ~20 consultas de datasheet.
- Pendente no `SAMSUNG.md`: corrigir o `46`=x4 (linha 109) e conferir K4W.

**Arquivos que você herda (raiz do repo):**

- `COLETAR_largura_bits.py` — o coletor. Genérico menos uma função.
- `LARGURA_samsung.xlsx` / `.csv` — o entregável da Samsung.
- `PROMPT_chat_Samsung_largura_2026-09-12.md` — molde de prompt para chat de marca.

---

## 7. As marcas que faltam

Com yaml no repo: `esmt`, `foresee`, `gigadevice`, `hynix`, `isocom`,
`kingston`, `micron`, `nanya`, `piecemakers`, `rayson`, `sandisk`,
`toshiba-kioxia`, `winbond`.

**Não siga esta ordem nem a alfabética.** Antes de escolher, meça — uma consulta
resolve:

```python
# quantos PNs de DRAM DISCRETA cada marca tem, e quanto de largura ja existe
from chips.models import KnownPart
from collections import Counter
qs = KnownPart.objects.exclude(chip_type='')
Counter((k.brand.name, bool(k.bus_width)) for k in qs
        if k.chip_type.upper().startswith(('DDR','SDRAM'))
        and not k.chip_type.upper().startswith('LPDDR'))
```

(ou, mais curto e já separado pelo que vale dinheiro: `VERIFICAR_largura.py`)

Ataque primeiro a marca com **muitos PNs de DRAM discreta e bastante `bus_width`
já preenchido** — é ela que dá prova rápida. Marca com muito PN e nenhuma largura
dá trabalho de datasheet antes de dar resultado; marca com poucos PNs não paga o
custo de pesquisar a gramática.

**Fila medida em 2026-09-20, depois da Samsung fechar:** SK Hynix 52 (DDR3 22 ·
DDR4 11 · DDR3L 9 · DDR2 6 · DDR1 3 · DDR5 1) · Micron 44 (**42 são DDR2**, fora
do mercado — sobram 2) · Rayson 11 · Samsung 2 (RDRAM, outro esquema de PN) ·
PieceMakers 1 · Toshiba 1. **SK Hynix é a próxima.**

Kingston, SanDisk e Toshiba-Kioxia são majoritariamente NAND/eMMC — provavelmente
fora de escopo. **Confirme pelos dados antes de descartar.**

---

## 8. O que NÃO fazer

- ❌ Preencher `bus_width` decodificando o PN (seção 3) — salvo pelo
  decodificador OFICIAL da marca, e aí os PNs saem da contagem de prova.
- ❌ Pôr largura no `interface`. Desde 2026-09 é campo de protocolo; o portão
  recusa e a Fase 5 põe uma constraint no banco.
- ❌ Baixar `MIN_PROVAS` / `MIN_LARGURAS` para a planilha crescer.
- ❌ Aplicar a gramática de uma marca em outra.
- ❌ Confiar no `.md` interno acima da fonte primária.
- ❌ Gravar `known_part` pelo yaml: o canal é `submit_known_parts` (Opção 2). O
  yaml → `load_brands` é para GRAMÁTICA e largura de FAMÍLIA.
- ❌ Usar a gramática como régua de preço ou rentabilidade. Ela serve para dar um
  palpite rápido sobre PN novo na bancada; a tela mostra "lido do PN" justamente
  para o operador saber que aquilo não é datasheet.
- ❌ Rodar `--commit` você mesmo. Prepare, explique, entregue com dry-run.
- ❌ Concluir "está tudo certo" a partir de uma leitura que devolveu zero.
- ❌ Gastar esforço em GDDR — é sucata, decisão do dono.
- ❌ Entregar planilha sem a coluna `PROVA`. Sem ela, ninguém consegue escolher
  onde cortar daqui a seis meses, e a planilha inteira vira "confie em mim".
