# Prompt de design — Tela de triagem de chips (WhatTheChip / eMiner)

> Cole este texto no Claude (modo design) junto com os prints do estoque. Ele
> descreve TODO o fluxo e TODOS os estados, para a página ser recriada cobrindo
> cada situação possível. Idioma da interface: **português (Brasil)**.

---

## 1. Contexto

**WhatTheChip** é a ferramenta de bancada da **eMiner** (reciclagem/refurbishing de
eletrônicos). Um **operador de bancada** pega um chip de memória recuperado, lê o
código gravado a laser nele, digita/escaneia na tela e recebe **na hora**:

1. **O que é o chip** (tipo, capacidade, marca) e
2. **Para onde ele vai** — uma de 4 caixas físicas, com a decisão de **manter ou
   descartar**.

A tela é uma ferramenta de **triagem rápida e repetitiva**. O operador faz isso
centenas de vezes por turno. Pode ser idoso, pode usar **tablet**. Prioridade
absoluta: **clareza, alvos grandes, zero ambiguidade**.

## 2. Objetivo e hierarquia da tela

- **Herói da tela:** o campo de **Part Number** (entrada) e o **card de resultado**
  que aparece logo abaixo. É aqui que o operador vive 95% do tempo.
- **Secundário (consultar, esporádico):** a **lista do estoque** do lote, com busca,
  filtros e os botões Exportar/Fechar. Fica **mais abaixo na página**, sob o título
  "Estado atual do lote", separada por um divisor. Não precisa estar visível sem
  rolar.

## 3. Princípios de design (obrigatórios)

- **IBM Carbon (tema White, claro fixo).** Sem modo escuro.
- **Limpo tipo Google:** muito espaço em branco, **sem caixas/bordas** ao redor dos
  blocos de conteúdo. O que dá cor e foco é o **retângulo grande do destino**, não
  contêineres.
- **Elementos grandes** (toque/tablet/idoso): campo de PN enorme, botões altos,
  linhas de tabela altas, fontes generosas.
- **Largura máxima ~1200px**, conteúdo centralizado (não esticar em 4K).
- **Navegação:** uma única **barra horizontal no topo** (sem sidebar).
- **Cantos retos** (border-radius 0–2px, padrão Carbon).

## 4. Design system — tokens

- **Fontes:** "Helvetica Neue" (texto); **"IBM Plex Mono"** para Part Numbers e
  rótulos de caixa.
- **Cores base:** fundo branco `#ffffff`; superfícies cinza `#f4f4f4` / `#e0e0e0`;
  texto `#161616` / secundário `#525252` / auxiliar `#6f6f6f`.
- **Azul de ação (primário):** Carbon Blue `#0f62fe` (hover `#0353e9`).
- **Status:** sucesso `#198038` (bg `#defbe6`); alerta `#b28600` (bg `#fff8e1`,
  borda `#f1c21b`); erro `#da1e28` (bg `#fff1f1`); info `#0043ce` (bg `#edf5ff`).
- **Laranja de destaque:** `#ff832b` (hover `#eb6200`).
- **Espaçamento base 8px** (4, 8, 12, 16, 24, 32, 48, 64, 80, 96).

## 5. O fluxo — "porteiro de 3 etapas" + verificação de digitação

O operador digita o PN (mínimo 4 caracteres) e pressiona Enter / "Decodificar". O
sistema classifica e roda **3 perguntas em ordem; a primeira que falha decide o
destino**:

```
1) IDENTIFICAÇÃO  — eu reconheci o chip (tenho specs reais)?
      └─ NÃO →  DESCONHECIDO
2) FONTE          — está CONFIRMADO no banco (fonte humana/oficial)?
      └─ NÃO →  FILA
3) RENTABILIDADE  — vale a pena vender?
      ├─ NÃO RENTÁVEL          →  REPROVADO
      └─ RENTÁVEL ou INDETERMINADO →  APROVADO   (regra conservadora:
                                                  na dúvida, aprova)
```

Em **paralelo** (qualquer etapa): se o que foi digitado **se parece muito** com um
PN confirmado conhecido, mostra um **banner de sugestão de digitação** ("você quis
dizer?"). Não é uma etapa do funil — é uma rede de segurança contra erro de digitação.

## 6. Os 4 destinos

| Destino | Cor | Significado | Botão de ação | Cor do botão |
|---|---|---|---|---|
| ✓ **APROVADO** | verde | Reconhecido, confirmado e com liquidez. Entra no estoque. | **+ Adicionar ao estoque** | azul `#0f62fe` |
| ⏳ **FILA** | amarelo/âmbar | Reconhecido só por dedução (gramática), não confirmado. Vai para a fila de revisão do gestor. | **⏳ Enviar para conferência** | amarelo (bg `#fff8e1`, texto `#b28600`, borda `#f1c21b`) |
| ✗ **REPROVADO** | vermelho | Confirmado, mas NÃO RENTÁVEL. Bloqueado — vai para resíduo eletrônico. | **✗ Registrar descarte** | vermelho `#da1e28`, texto branco |
| ? **DESCONHECIDO** | cinza | O sistema não reconheceu. Registra para análise futura. | **Registrar como desconhecido** | **laranja `#ff832b`**, texto escuro |

Em **todos**: botão **Cancelar** = **só borda preta, sem fundo** (nunca compete
visualmente com a ação principal) e um botão **📋** (copia diagnóstico para o
clipboard). Em aprovado/fila/reprovado há também um campo **Qtd.** (quantidade).

## 7. Anatomia do card de resultado (de cima para baixo)

1. **Cabeçalho:** rótulo de status (✓ Aprovado / ⏳ Fila de conferência / ✗ Reprovado
   / ? Não identificado) à esquerda, **Part Number** (mono, azul) à direita.
2. **Barra de 3 etapas:** três blocos lado a lado — `1 Reconheci`, `2 Confirmado`,
   `3 Rentável` — cada um com estado:
   - **pass** (verde, ✓), **fail** (vermelho, ✗), **skip** (cinza, ·).
   - Ex.: FILA mostra `1 ✓` `2 ✗` `3 ·`. REPROVADO mostra `1 ✓` `2 ✓` `3 ✗`.
3. **Retângulo grande do destino** — a informação principal. Texto enorme (mono).
   Para APROVADO é o **código da caixa física** (ver §8). Para os outros é a palavra
   do destino. **Sem frase explicativa abaixo no caso APROVADO** (só o rótulo).
4. **Botões** (conforme §6).

**Importante (NÃO fazer):** sem "pills"/etiquetas de meta-info (estoque, confiança,
rentabilidade) — elas poluem e são redundantes com a barra de etapas. Sem contêiner
com borda/caixa ao redor do card — o conteúdo fica direto na página.

## 8. Caixas físicas de destino (APROVADO) — cor + rótulo

O retângulo grande indica em qual caixa física o chip vai. Cor por tecnologia:

| Tecnologia | Cor do retângulo | Rótulo (exemplos) |
|---|---|---|
| eMCP | vermelho `#da1e28` (texto branco) | `EMCP16+1.5` (NAND 16GB + RAM 1.5GB) |
| uMCP | rosa `#ff7eb6` (texto escuro) | `UMCP128+6` |
| UFS | amarelo `#f1c21b` (texto escuro) | `UFS128GB` |
| eMMC | verde `#42be65` (texto escuro) | `EMMC32GB` |
| LPDDR / DDR | azul `#4589ff` (texto branco) | `LPDDR4+4GB` ou `RAM` |
| NAND flash | roxo `#8a3ffc` (texto branco) | `NAND 64GB` |

Para os outros destinos, o retângulo é: **FILA** = laranja `#ff832b`; **REPROVADO**
= vermelho escuro `#750e13`; **DESCONHECIDO** = cinza com borda tracejada e um grande
"?".

## 9. Banner de sugestão de digitação (precisa ter DESTAQUE)

Quando há sugestões, aparece um bloco bem chamativo (não discreto):

- Fundo âmbar `#fff8e1`, **borda 2px** `#f1c21b`, **barra esquerda grossa laranja**
  (~10px `#ff832b`), sombra.
- Título em caixa-alta, ~16px: **"⚠ Confira a digitação — você quis dizer?"**
- Cada sugestão é um item clicável grande (~18px, mono): o PN sugerido + "usar este →"
  à direita. Ex.: `SDIN7DU28G   usar este →`.
- Clicar substitui o PN digitado e reclassifica.

## 10. Cabeçalho do lote (topo do conteúdo)

- Breadcrumb: `← Lotes / Lote #039`.
- Título: **Lote #039** + selo de status (`ABERTO` verde / `Fechado` cinza).
- Subtítulo/descrição: ex. `EMINER MOBILE`.
- Se o lote estiver **fechado**: banner de aviso "🔒 Este lote está fechado…".

## 11. Seção "Estado atual do lote" (secundária, mais abaixo)

Separada do topo por bastante espaço + um divisor (linha) + o título **"Estado atual
do lote"**. Contém, nesta ordem:

- Linha de controles: **Buscar PN** (input), **Tipo** (select: Todos/eMCP/uMCP/eMMC/
  UFS/RAM/NAND) à esquerda; **Exportar .xlsx** e **Fechar Lote** à direita.
- Contador: `118 tipos · 562 un. total`.
- **Tabela** de estoque, colunas: **Part Number** (mono, azul) · **Tipo** (etiqueta
  azul) · **Fabricante** · **Capacidade** · **Interface** · **Qtd.** (badge) ·
  **Última adição** (data/hora mono) · **[lixeira vermelha]** (remover).
- Estado vazio: ícone + "Nenhum chip no estoque".

## 12. Regras de rentabilidade (para mocks realistas)

- **eMCP / uMCP:** rentável se NAND ≥ 8GB **e** RAM ≥ 1GB **e** LPDDR3 ou superior;
  senão NÃO RENTÁVEL.
- **eMMC / UFS:** rentável se ≥ 8GB; senão NÃO RENTÁVEL.
- **LPDDR avulso:** LPDDR3+ e ≥ 2GB → rentável.
- **DDR avulso:** DDR3+ e densidade ≥ 2Gb → rentável; DDR2 ou menos → NÃO RENTÁVEL.
- **Outros tipos sem regra (NOR, SoC, SDRAM…):** INDETERMINADO → vai para APROVADO.

## 13. TODOS os estados para simular (cubra cada um)

**Entrada:**
1. Vazio (placeholder "EX: KMQ310006M-B421").
2. Digitando < 4 caracteres (nada acontece).

**Resultado (card):**
3. **APROVADO rentável** — ex. eMCP confirmado (retângulo vermelho `EMCP16+1.5`,
   barra `✓ ✓ ✓`, botão azul Adicionar).
4. **APROVADO indeterminado** — tipo sem regra, confirmado (barra `✓ ✓ ✓`, sem
   veredito de rentabilidade, mesmo botão azul).
5. **FILA** — reconhecido por gramática, não confirmado (retângulo laranja FILA,
   barra `✓ ✗ ·`, botão amarelo Enviar para conferência).
6. **REPROVADO** — confirmado e NÃO RENTÁVEL (retângulo vermelho escuro REPROVADO,
   barra `✓ ✓ ✗`, botão vermelho Registrar descarte).
7. **DESCONHECIDO** — não reconhecido (retângulo cinza "?", barra `✗ · ·`, botão
   laranja Registrar como desconhecido).
8. **Qualquer um acima + banner de sugestão de digitação** (item 9 visível).

**Feedback após enviar (substitui o card):**
9. Adicionado ao estoque (toast/confirmação + tabela atualiza).
10. Enviado para a fila de conferência.
11. Registrado como reprovado (resíduo).
12. Registrado como desconhecido.

**Lote / tabela:**
13. Lote **aberto** (selo verde) e lote **fechado** (selo cinza + banner + sem
    adicionar).
14. Tabela com itens (use os dados de §14) e tabela **vazia**.

## 14. Dados de exemplo (para popular os mocks)

Lote **#039 — EMINER MOBILE — ABERTO**, `118 tipos · 562 un. total`. Linhas:

| Part Number | Tipo | Fabricante | Capacidade | Interface | Qtd. |
|---|---|---|---|---|---|
| KMFNX0012M | eMCP | Samsung | eMMC 5.1 8GB / LPDDR3 1GB | LPDDR3 | 37 |
| KMRX1000BM | eMCP | Samsung | eMMC 5.1 32GB / LPDDR3 3GB | LPDDR3 | 1 |
| KMQ310006B | eMCP | Samsung | eMMC 5.1 16GB / LPDDR3 1.5GB | LPDDR3 | 23 |
| KMFN10012A | eMCP | Samsung | eMMC 5.1 8GB / LPDDR3 1GB | LPDDR3 | 16 |
| SDIN7DU2-8G | eMMC | SanDisk | 8GB | eMMC 4.5/5.0/5.1 | 10 |
| KMQN10006B | eMCP | Samsung | eMMC 5.1 8GB / LPDDR3 1GB | LPDDR3 | 28 |

Exemplos por destino: APROVADO → `KMQ310006B` (EMCP16+1.5). DESCONHECIDO + sugestão →
digitar `SDIN7DU2-8X` e sugerir `SDIN7DU28G`.

## 15. O que NÃO fazer (erros a evitar)

- Sem modo escuro; sem alternador de tema.
- Sem contêiner/caixa com borda ao redor do card de resultado nem da área de entrada.
- Sem o título "Adicionar chip" e sem o texto de ajuda "Clique Decodificar ou
  pressione Enter".
- Sem "pills" de meta-info no card.
- Links visitados **não** podem ficar roxos (devem manter a cor normal).
- "Cancelar" nunca com fundo colorido (só borda preta), para não ser confundido com a
  ação principal.
- Não encher a tela: a lista do estoque é secundária e fica **abaixo**, sob "Estado
  atual do lote".
