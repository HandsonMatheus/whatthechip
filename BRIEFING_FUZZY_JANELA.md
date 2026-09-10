# BRIEFING — fuzzy: alinhamento por janela + matriz de confusão

> Prompt para o **chat de fuzzy** do WhatTheChip. Cole inteiro numa conversa nova.
> Origem: sessão da bancada de OCR (`ocr_bench/`), 2026-08-27. Tudo aqui foi
> **medido** contra os 8.601 `KnownPart` approved do banco local, não estimado.

---

## 0. Antes de tocar em qualquer coisa

Leia, nesta ordem:

1. **`CLAUDE.md`** inteiro — regras de ouro, especialmente a #1 (o agente **não** roda
   comando que escreve no banco) e a convenção de idioma (código e comentários em português).
2. **`FUZZY.md`** inteiro — é a bíblia deste subsistema. Você vai alterá-lo no fim.
3. **`chips/engine.py`**, funções `_visual_edit_distance` (L85), `_fuzzy_candidates` (L165),
   `_prefix_candidates` (L195), `_combined_suggestions` (L240), `_fuzzy_fbga_candidates` (L269).
4. **`AUTORIA.md`** — o contrato de entrega (testes de regressão, o dono é quem publica).
5. Opcional, para contexto: `BRAINSTORM_OCR_BANCADA.md` §4.3b e `ocr_bench/index.html`
   (a implementação de referência em JS, já rodando).

**Regra que vale o tempo todo:** *não modifique código sem perguntar*. Traga a proposta,
os testes e os números; quem decide e quem roda é o dono.

---

## 1. O achado

`_prefix_candidates` casa por **`startswith`**. Isso cobre o PN **truncado no FIM** — que é o
erro de quem **digita** e para antes do sufixo (`H5TQ2G83` → `H5TQ2G83CFR`).

O erro de quem **lê o chip com o PN parcialmente coberto** é o oposto: falta o **COMEÇO**.
Aconteceu ao vivo na bancada: o operador fotografou um `NT5CC512M8EN-EK` (Nanya DDR3L 4Gb,
**está no banco, approved**) com o dedo tapando o início e o quadro cortando o fim. A leitura
foi `5CC512M8EN-`. O sistema devolveu **nenhum candidato**.

Por quê, exatamente:

| Caminho | Por que não pegou |
|---|---|
| `_prefix_candidates` | `5CC512M8EN-` não é prefixo de ninguém — `startswith` falha |
| `_fuzzy_candidates` | filtra `abs(len(cand) - len(pn)) > threshold`; 11 vs 15 = **4** > 2 → descartado antes de comparar |

E não é caso raro nem exclusivo do OCR: **hoje, quem digita a partir do meio de um PN na busca
não acha nada.** É o mesmo buraco.

---

## 2. A correção proposta: alinhamento semi-global ("janela")

A leitura precisa casar **inteira**, mas pode sentar em **qualquer posição** do candidato —
pular o começo e o fim do candidato sai **de graça**. Score final soma o que ficou de fora:

```
score = custo_de_alinhamento_na_janela  +  |len(cand) - len(pn)| * CUSTO_FALTA
```

com `CUSTO_FALTA = 0.35` (calibrado na bancada: põe uma completude de 4 caracteres em 1.40,
competindo de igual pra igual com um erro visual arbitrário de 1.0 — que é o comportamento
desejado).

A mudança na DP em relação ao `_visual_edit_distance` atual são **duas linhas**:

* linha 0 (`d[0][j]`) começa em **0** em vez de `j` → pular o início do candidato é grátis;
* o resultado é o **mínimo da última linha** em vez da última célula → pular o fim é grátis.

O custo de substituição continua vindo da `_CHIP_VISUAL_COST` — nada muda ali.

### Implementação de referência (JS, já testada na bancada — portar para Python)

```javascript
function vedJanela(a, b){
  var curta = a.length <= b.length ? a : b;
  var longa = a.length <= b.length ? b : a;
  var n = curta.length, m = longa.length, i, j, tmp;
  if (!n) return 0;
  var prev = new Float64Array(n + 1), curr = new Float64Array(n + 1);
  for (i = 0; i <= n; i++) prev[i] = i;      // coluna 0: consumir a curta custa 1 cada
  var melhor = prev[n];
  for (j = 0; j < m; j++){
    var cb = longa.charCodeAt(j);
    curr[0] = 0;                              // linha 0: pular a longa é DE GRAÇA
    for (i = 0; i < n; i++){
      var sub = custoVisual(curta[i], longa[j]);   // = _CHIP_VISUAL_COST
      var v = prev[i] + sub;
      var w = prev[i+1] + 1;   if (w < v) v = w;
      var z = curr[i] + 1;     if (z < v) v = z;
      curr[i+1] = v;
    }
    if (curr[n] < melhor) melhor = curr[n];   // fim livre: melhor janela vence
    tmp = prev; prev = curr; curr = tmp;
  }
  return melhor;
}
```

Note que a função é **simétrica**: também cobre o caso inverso, em que a string digitada/lida
tem **lixo em volta** do PN. Isso é de graça e é bom.

---

## 3. Resultados medidos (8.601 PNs approved, banco local, 2026-08-27)

### Leitura/digitação parcial — o que a janela conserta

| Cenário | top-1 | top-3 | fora da lista |
|---|---|---|---|
| faltam **2 do começo** | **99,3%** | 99,3% | 0% |
| faltam **3 do começo** | **99,3%** | 99,3% | 0% |
| faltam 2 de **cada ponta** | 76,0% | 92,0% | 0% |
| faltam 3 do começo + 2 do fim | 74,0% | 90,7% | 0% |

**Sem a janela, os quatro cenários dão 0% quando a diferença de comprimento passa de 3.**

### A assimetria — vale virar linha no `FUZZY.md`

**Perder o começo é quase de graça; perder o fim custa caro.** O miolo do PN já é
discriminante; o **sufixo** é onde as variantes se separam (`NT5CC512M8EN-**DI**` ×
`NT5CC512M8EN-**EK**`). Quando o fim falta, o sistema **empata os dois de propósito** — a
informação não está na entrada, e a escolha é humana. Isso não é bug, é o comportamento certo,
e reforça a regra de UI que já existe: mostrar o vencedor **e** as alternativas.

Repare que **fora-da-lista é 0% nos quatro cenários**: o certo sempre aparece na lista.

### Regressão — o caminho normal não pode piorar

| Erros de caractere | antes | depois da janela |
|---|---|---|
| 1 erro | 98,8% | 98,8% |
| 2 erros | 94,8% | 94,7% |
| 3 erros | 93,6% | 92,0% |

(diferenças dentro do ruído amostral; modelo de erro: 45% confusão visual, 25% substituição
arbitrária, 15% deleção, 15% inserção)

---

## 4. Performance — o índice não é opcional

A janela é **O(n×m) por candidato**. Rodada contra o corpus inteiro custou **3,5 segundos**
para 12 consultas. Inaceitável na bancada.

A solução que funcionou: **índice invertido de trigramas**. Só entra na DP quem compartilha
**≥ 2 trigramas** com a entrada. Um erro de OCR/digitação mata no máximo 3 trigramas, então a
barra de 2 sobreviventes passa a leitura real e barra o resto do catálogo.

**3.568 ms → 361 ms**, resultado idêntico.

```javascript
// montado UMA vez sobre o corpus
var TRIGRAMAS = {};                  // trigrama -> [índices]
for (var i = 0; i < PNS.length; i++){
  var p = PNS[i], vistos = {};
  for (var j = 0; j + 3 <= p.length; j++){
    var g = p.substr(j, 3);
    if (vistos[g]) continue;
    vistos[g] = 1;
    (TRIGRAMAS[g] || (TRIGRAMAS[g] = [])).push(i);
  }
}

// por consulta: só quem compartilha >= MIN_GRAMAS entra na DP
function candidatosPorGrama(h){
  var conta = new Map();
  for (var j = 0; j + 3 <= h.length; j++){
    var lista = TRIGRAMAS[h.substr(j, 3)];
    if (!lista) continue;
    for (var q = 0; q < lista.length; q++)
      conta.set(lista[q], (conta.get(lista[q]) || 0) + 1);
  }
  var out = [];
  conta.forEach(function(n, i){ if (n >= 2) out.push(PNS[i]); });
  return out;
}
```

**Em Python/Django isso precisa de decisão de arquitetura, e é o ponto mais delicado da
tarefa.** Opções a avaliar e trazer com prós e contras — não escolha sozinho:

* **`pg_trgm` no Postgres** (`CREATE EXTENSION pg_trgm` + índice GIN em `part_number`, filtro
  por `%` ou `similarity()`). É o caminho nativo: o banco faz o pré-filtro, o Python roda a DP
  só nos sobreviventes. Exige migration e a extensão disponível no Render.
* **Índice em memória** no mesmo lugar onde o catálogo já é cacheado por `catalog_version`
  (regra de ouro #3 — o cache recarrega sozinho). Zero mudança no banco, mas custa RAM no
  worker e precisa invalidar junto com o catálogo.
* **Só o filtro de comprimento**, alargando a janela de ±3 — mais simples, mas foi exatamente
  isso que deu 3,5 s. Provavelmente não fecha a conta; medir antes de descartar.

Meça a latência real da busca com **8.601+ registros** antes e depois. O `classify()` está no
caminho quente da bancada: se a busca passar de ~300 ms, o operador sente.

---

## 5. Dois itens menores, no mesmo escopo

### 5.1 Candidatos novos para a `_CHIP_VISUAL_COST`

Na primeira sessão real da bancada, o OCR leu **`7` onde era `1`**, repetidamente — e `1↔7`
**não está na matriz**. `6↔7` também apareceu. Um `1` com serifa/base em marcação a laser vira
`7` com facilidade, e o caso é simétrico ao `1↔I` que já existe (0.1).

**Não adicione por conta própria.** O `FUZZY.md` §9 já define o processo de adicionar par de
confusão — siga-o, e traga a proposta com evidência. A bancada gera o histograma de
`lido→certo` automaticamente e marca com ✦ os pares que ainda não estão na matriz; peça ao
dono o CSV de amostras antes de propor. Uma leitura só não é evidência.

### 5.2 `_fuzzy_fbga_candidates` — conferir se é realmente alcançado

Na bancada eu portei o lookup **exato** de FBGA e esqueci o fuzzy. O efeito foi brutal: com
**1 erro** num código FBGA, a recuperação caiu para **0,8%** — porque o código tem 5 caracteres
e os PNs têm 10-20, então nenhuma outra etapa alcança o registro certo. Com o fuzzy, subiu para
59,5%.

O engine **tem** `_fuzzy_fbga_candidates` (L269) e ele é chamado em L1690. **Confirme com um
teste** que um FBGA com 1 caractere errado realmente chega lá e devolve sugestão — é uma falha
silenciosa e cara se não chegar.

Contexto para calibrar expectativa (medido): o espaço FBGA é **denso** — 99,3% dos 6.624
códigos têm ao menos um vizinho a distância visual ≤ 1.0, com média de **17,3 vizinhos**. Cinco
caracteres não têm redundância. Mesmo com o fuzzy funcionando, 26% dos casos com 1 erro ficam
fora do top-8. Isso é limite de informação, não bug — mas o **usuário precisa ver** que a
sugestão de FBGA é menos confiável que a de PN completo. Vale pensar em como sinalizar isso.

⚠ E não generalize a partir do FBGA: **ele é exclusivo da Micron** (6.624 de 6.624 códigos), e
as outras onze marcas do catálogo têm **zero**.

---

## 6. O que entregar

1. **Proposta escrita antes do código**: qual estratégia de índice, por quê, e o custo medido.
2. Se aprovada: a implementação em `chips/engine.py`, no estilo do arquivo (comentários em
   português explicando o **porquê**, não o quê).
3. **Testes de regressão em `chips/tests.py`**, cobrindo no mínimo:
   * PN com o **começo** faltando encontra o registro certo (o caso `NT5CC512M8EN-EK`);
   * PN com o **fim** faltando continua funcionando como hoje (não regredir o `startswith`);
   * PN com lixo em volta encontra o registro;
   * os casos de typo que já passam **continuam passando** — a suíte inteira verde:
     `python manage.py test chips estoque --settings=core.settings_test`
   * `characterize_baseline --diff` mostrando **só** o pretendido.
4. **`FUZZY.md` atualizado**: nova subseção em §3, a assimetria começo×fim em §10
   (Limitações conhecidas) ou §11 (Histórico), e os parâmetros novos em §8 (tuning).
5. Os números medidos antes/depois, para o dono comparar com os desta tabela.

---

## 7. O que NÃO fazer

* **Não** rodar nada que escreva no banco (regra de ouro #1) — proponha, o dono executa.
* **Não** mexer no `ocr_bench/` — é bancada de medição descartável, fora do Django, e não é o
  seu escopo. Ela é a **fonte** deste briefing, não o alvo.
* **Não** alterar `_visual_edit_distance` nem a `_CHIP_VISUAL_COST` sem processo (§5.1).
* **Não** afrouxar o gate de confiança (`_SUGGESTION_CONFIDENCE`) para "achar mais" — o
  problema é o algoritmo de casamento, não o filtro de confiança.
* **Não** subir o `threshold` do `_fuzzy_candidates` como atalho para o mesmo efeito: alargar a
  janela de comprimento foi medido e custa 3,5 s.
* **Não** deixar a busca do operador mais lenta que ~300 ms. Se a janela não couber no
  orçamento, é melhor entregar ela **só no caminho de sugestão** (quando o PN já não foi
  encontrado) do que degradar o caminho feliz.

---

## 8. Uma pergunta em aberto para o dono

A janela vale para **toda** busca ou só para o caminho de sugestão? Hoje `_combined_suggestions`
só roda quando o PN **não** foi encontrado (`pn_not_in_db` / prefixo desconhecido), então
provavelmente o custo já está no caminho frio — o que é ótimo. **Confirme isso lendo
`classify()` (L1690, L1745, L1757) antes de desenhar a solução**, porque muda completamente o
orçamento de latência.
