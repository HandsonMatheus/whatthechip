> ⚠ **ATUALIZADO EM 2026-09-20.** Este prompt foi escrito quando a largura morava
> no campo `interface`. Ela agora tem campo próprio, **`bus_width`**, e o portão
> RECUSA largura no `interface` (PLANO_BUS_WIDTH.md). Duas coisas mais mudaram:
> o canal é `submit_known_parts <arquivo> --fill-empty` — **não** yaml →
> `load_brands`, que é só para gramática e largura de família; e o **decodificador
> oficial de part number publicado pela marca vale como Tier-1** (decisão do dono),
> desde que os PNs assim preenchidos saiam da contagem de prova do coletor.

# Para o chat da SAMSUNG — preencher `bus_width` (largura de barramento)

Estamos montando uma feature que precisa separar chips de **4 e 8 bits** dos de
16 bits. O levantamento que você fez em `samsung_k4b_x4_x8_levantamento.xlsx`
está **correto** — conferimos PN a PN contra um método independente e deu **zero
divergência de largura** nos 52 em comum. E a nota de rodapé que você deixou no
arquivo, avisando que a lista vinha só da visibilidade local, estava certa: o
banco tem mais.

Agora precisamos de você para uma coisa específica e pequena.

---

## ⚠ A REGRA DE OURO DESTE TRABALHO — leia antes de tudo

O `bus_width` desses PNs **NÃO pode ser preenchido decodificando o part number.**

Existe um coletor (`COLETAR_largura_bits.py`) que deduz a largura pela posição no
PN e depois **cruza** com o campo `bus_width` do banco. Esse cruzamento é o que
autoriza confiar na dedução: se as duas leituras vêm de origens independentes e
concordam 100 vezes sem um contraexemplo, a regra está provada.

Se você preencher o `bus_width` usando a regra, o cruzamento vira a regra
concordando **com ela mesma**. O número de acordos sobe, o script promove a
família, a planilha ganha linhas — e nada disso prova coisa nenhuma. Seria o
pior resultado possível: errado com aparência de verificado.

**Todo `bus_width` que você escrever tem que vir de datasheet, página oficial da
Samsung ou distribuidor Tier-1 — a mesma fonte que você já cita nas `notes`.**
Se para um PN você não achar fonte, **deixe vazio**. Vazio é um resultado
honesto; chute não é.

---

## O que preencher

Campo `bus_width` do `known_part`, com **só a largura**: `x4`, `x8`, `x16` ou
`x32`. Nada de geração de RAM ali (`chips/conventions.py` já trava isso), nada de
`"x8 @ 1600MTPS"` — só o token.

Pela TRAVA DE ESCRITA: edite `chips/knowledge/samsung.yaml` (ou uma submissão em
`submissions/`) e grave com `load_brands --brand samsung --commit`. Nunca direto
no banco.

E como sempre: `notes` com a fonte, `source_url` com o link.

---

## Prioridade — o retorno NÃO é uniforme

Medimos quanto cada família rende **de verdade** em linha de planilha:

| família | travados | viram x4/x8 | quanto pesquisar | ouro ganho |
|---------|---------:|------------:|------------------|-----------:|
| **K4A** (DDR4) | 61 | 34 | 5 PNs, ≥2 larguras | **+34** |
| **K4R** (DDR5) | 21 | 14 | 5 PNs, ≥2 larguras | **+14** |
| **K4T** (DDR2) | 14 | 5  | 5 PNs, ≥2 larguras | **+5** |
| K4H (DDR1) | 5 | 2 | **os 5** (família pequena) | +2 |
| K4D · K4G · K4J · K4W · K4Z · K4N | 72 | **0** | — | **0** |

### ❌ NÃO gaste tempo com K4D, K4G, K4J, K4W, K4Z, K4N

São 72 PNs e **nenhum deles é x4 ou x8** — é tudo x16 e x32 (GDDR e DDR
gráfico). Mesmo com o `bus_width` perfeitamente preenchido, a planilha de 4/8
bits não ganha **uma linha sequer**. Preencher ali é trabalho com zero retorno
para esta feature. (Se quiser preencher por completude do catálogo, ótimo — só
não confunda com esta tarefa.)

### ⚠ K4H é a pior relação esforço/retorno

A família inteira tem 5 PNs, e a barra do coletor pede 5 acordos. Ou seja: só
promove com **100% de cobertura**, para ganhar 2 linhas. Deixe por último.

---

## Critério de pronto, por família

Uma família só é promovida quando, no banco, tiver:

- **≥ 5 PNs** com `bus_width` preenchido de fonte Tier-1;
- **0 divergências** contra a leitura posicional;
- acordo em **≥ 2 larguras distintas** — 5 PNs todos x16 não provam nada, porque
  a regra nunca precisou discriminar. Pegue pelo menos um x4 ou x8 e um x16.

Depois do `load_brands --commit`, o dono roda o coletor e a família se promove
**sozinha** — ninguém precisa editar código nem lista nenhuma.

---

## PNs sugeridos (todos existem no banco dele)

Escolhi PNs "base", sem sufixo de velocidade, que costumam ter datasheet direto.

**K4A — DDR4 (prioridade 1)**
- x4 : `K4A4G045WDBC`, `K4A8G045WBBC`
- x8 : `K4A4G085WE`, `K4A8G085WB`, `K4A8G085WC`
- x16: `K4A4G165WE`, `K4A8G165WB`, `K4A8G165WC`

> `K4A8G165WC` já está confirmado: a spec oficial da Samsung
> (*x16 only_8G_C_DDR4_Samsung_Spec_Rev1.5*) declara **512Mx16**. Um a menos.

**K4R — DDR5 (prioridade 2)**
- x4 : `K4RBH046VM`, `K4RCH046VM`
- x8 : `K4RAH086VB`, `K4RAH086VE`, `K4RAH086VP`
- x16: `K4RAH165VB`, `K4RAH165VP`

**K4T — DDR2 (prioridade 3)**
- x8 : `K4T1G083QJ`, `K4T1G084QJ`, `K4T51083QN`
- x16: `K4T1G163QJ`, `K4T1G164QJ`, `K4T51163QN`

**K4H — DDR1 (por último)**
- `K4H510438G`, `K4H510838G`, `K4H511638G`, `K4H561638D`, `K4H561638DTCB3`

---

## De passagem: dois pontos do SAMSUNG.md que precisam de conferência

**1. Linha 109 está errada.** Ela diz:

```
bus width em pn[5:7] (08=x8 · 16=x16 · 04/46=x4)
```

O `46` **não é largura** — é bancos + interface do DDR3, e é idêntico em x4, x8 e
x16. Qualquer código que caia nesse ramo carimba "x4" em tudo. A tabela correta,
do decodificador oficial da Samsung (fev/2009) e confirmada no DDR3 Product
Guide, é:

```
04 = x4    06 = x4 STACK    08 = x8
16 = x16   07 = x8 STACK    32 = x32
```

Os códigos **06 e 07 (empilhados)** não estão documentados em lugar nenhum no
`.md` e são uma armadilha real: eletricamente são 4 e 8 bits, fisicamente são
outra coisa.

**2. K4W está classificado como GDDR3.** A Samsung publica datasheet de
`K4W4G1646B` como **DDR3**, e os 30 K4W do banco batem com a gramática de DDR3.
Vale conferir antes que a classificação errada contamine preço ou destino.

---

## Não faça

- ❌ Preencher `bus_width` a partir do PN (destrói o método — leia o topo).
- ❌ Inventar PN que não existe. `confidence=estimated` é filtrado de propósito:
  a largura de um PN inventado é ficção decodificada com precisão.
- ❌ Escrever `bus_width` com geração de RAM (`DDR4`) — é largura, só isso.
- ❌ Gravar direto no banco. yaml → `load_brands`, sempre.
