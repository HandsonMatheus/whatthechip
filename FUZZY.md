# FUZZY.md — Sugestão Inteligente de Part Numbers (WhatTheChip)

> **Bíblia técnica do sistema de fuzzy suggestion.**  
> Leia antes de tocar em `chips/engine.py` (funções `_fuzzy_*`, `_prefix_*`,
> `_combined_suggestions`, `_visual_edit_distance`) ou nos templates
> `confirm_card.html` / `decode_card.html`.

---

## 1. Por que existe

O operador de bancada lê o código gravado a laser num chip recuperado e digita
na busca. Dois erros são frequentes:

| Situação | Exemplo digitado | PN real |
|---|---|---|
| **Confusão visual de caractere** | `D9SGO` | `D9SGQ` (O ↔ Q em laser de baixa resolução) |
| **PN incompleto** | `H5TQ2G83` | `H5TQ2G83CFR` (sufixo de temperatura/grau cortado) |

O sistema padrão de Levenshtein trata `D9SGO → D9SGQ` e `D9SGO → D9SGB` como
distância idêntica (= 1) e ordena alfabeticamente — D9SGB vem primeiro, mas é a
sugestão errada. O Levenshtein também não conecta `H5TQ2G83` a `H5TQ2G83CFR`
porque a diferença de comprimento (3) ultrapassa o threshold de edição.

A solução está em dois mecanismos complementares, mais uma matriz de confusão
específica para chips IC.

---

## 2. Arquitetura

```
classify(pn)
  ├── Camada 1 (banco confirmado) — sem sugestão: PN foi encontrado
  ├── Camada 2 (gramática da família) — sugestão se pn_not_in_db ou pn_incomplete
  ├── FBGA desconhecido           — sugestão FBGA fuzzy
  └── Camada 3 (prefixo desconhecido) — sugestão sempre
                    │
                    ▼
         _combined_suggestions(pn)
           ├── _prefix_candidates(pn)  → startswith, sufixo ausente
           └── _fuzzy_candidates(pn)   → edição visual, typo
                    │
                    ▼
         lista de strings (PNs sugeridos, máx. 5)
         → fuzzy_suggestions no resultado JSON
```

Para FBGA: `_fuzzy_fbga_candidates(pn)` (busca em `fbga_code`, não em
`part_number`) é chamada diretamente, sem passar por `_combined_suggestions`.

---

## 3. Funções do engine (`chips/engine.py`)

### 3.1 `_CHIP_VISUAL_COST` — matriz de confusão

Dicionário com chaves `frozenset({char_a, char_b})` (simétrico por design) e
valor `float` entre 0.0 e 1.0 representando o custo de substituição.

```python
_CHIP_VISUAL_COST: dict = {
    frozenset({'O', '0'}): 0.1,   # O vs zero — confusão mais comum
    frozenset({'O', 'Q'}): 0.1,   # Q com cauda imperceptível em laser
    frozenset({'Q', '0'}): 0.1,   # Q vs zero (família circular)
    frozenset({'1', 'I'}): 0.1,   # 1 vs I maiúsculo
    frozenset({'B', '8'}): 0.1,   # B vs 8 — clássico em reciclagem
    frozenset({'L', '1'}): 0.2,   # L vs 1 sem serifa
    frozenset({'S', '5'}): 0.2,
    frozenset({'Z', '2'}): 0.2,
    frozenset({'M', 'W'}): 0.2,   # M vs W espelhado
    frozenset({'U', 'V'}): 0.3,
    frozenset({'C', 'G'}): 0.3,   # C vs G (arco quase fechado)
    frozenset({'D', '0'}): 0.3,   # D vs zero em monospace
    frozenset({'K', 'X'}): 0.4,   # K vs X em fontes comprimidas
}
```

Pares não listados → custo padrão `1.0` (substituição arbitrária).

### 3.2 `_visual_edit_distance(a, b) → float`

Programação dinâmica idêntica ao Levenshtein, com substituições ponderadas
pelo `_CHIP_VISUAL_COST`. Inserções e deleções sempre custam `1.0`.

Resultado para `D9SGO`:

| Candidato | Custo | Motivo |
|---|---|---|
| `D9SGQ` | 0.1 | O→Q, confusão visual máxima |
| `D9SG0` | 0.1 | O→0, confusão visual máxima |
| `D9SGB` | 1.0 | sem custo especial |
| `D9SGG` | 1.0 | sem custo especial |

`D9SGQ` e `D9SG0` aparecem **antes** dos vizinhos alfabéticos.

### 3.3 `_fuzzy_candidates(pn, threshold=2) → list[KnownPart]`

1. Busca todos os `KnownPart` com `confidence__in=("confirmed", "manual")`
2. Descarta candidatos com `abs(len(candidato) - len(pn)) > threshold` (early exit)
3. Calcula `_visual_edit_distance` para o restante
4. Ordena por custo; retorna até 5 objetos `KnownPart`

**`threshold=2`:** captura erros de 1 caractere com folga. Nunca eleva para ≥ 3
sem medir o ruído — o banco tem dezenas de milhares de PNs.

### 3.4 `_prefix_candidates(pn, min_prefix_len=7) → list[KnownPart]`

Faz `KnownPart.objects.filter(part_number__startswith=pn)` com
`confidence__in=("confirmed", "manual")`. Captura PNs cujo sufixo foi cortado
pelo operador — diferença de comprimento seria > 2 (invisível ao fuzzy).

**`min_prefix_len=7`:** evita ruído para prefixos muito curtos. PNs reais de chips
têm ≥ 7–8 caracteres; um prefixo de 4–5 letras poderia ser o início de centenas
de PNs distintos.

⚠ **ORDENAÇÃO É POR RELEVÂNCIA, NUNCA ALFABÉTICA** (corrigido 2026-08-24 — §11).
`.order_by(Length("part_number"), "part_number")[:_MAX_SUGESTOES]`: a completude
mais **curta** primeiro, porque é a mais próxima do que o operador digitou. Na
prática mostra as **revisões distintas** (`…46B`, `…46D`, `…46E`, `…46Q`) antes das
variantes longas de grade/embalagem de uma revisão só — que é a decisão que ele
precisa tomar primeiro. **Nunca volte para `.order_by("part_number")`**: alfabético
+ corte é o bug que escondia linhagens inteiras em silêncio.

### 3.5 `_combined_suggestions(pn) → list[str]`

Junta `_prefix_candidates` (mais certos — o digitado é literalmente o início do
PN real) + `_fuzzy_candidates` (typo), deduplica, retorna até `_MAX_SUGESTOES`
part_numbers como strings.

⚠ **Era um CORTE DUPLO:** `_prefix_candidates` cortava em 5 e este cortava o merge
em 5 de novo — então um PN base com 5+ variantes deixava o fuzzy com **zero vaga**.
Os dois tetos subiram juntos; se um dia baixar, baixe os dois com consciência disso.

### 3.6 `_fuzzy_fbga_candidates(pn, threshold=2) → list[str]`

Mesmo algoritmo que `_fuzzy_candidates`, mas busca no campo `fbga_code` em vez
de `part_number`. Retorna strings de FBGA (ex: `D9SGQ`), não PNs completos.
Chamado apenas quando o PN digitado bate o padrão FBGA
(`^[A-Z][A-Z0-9]{4}$`) e não está no banco.

---

## 4. Quando as sugestões são acionadas

| Camada no engine | Condição | Função chamada |
|---|---|---|
| **Gramática** (camada 2) | `pn_not_in_db=True` ou `pn_incomplete=True` | `_combined_suggestions(pn)` |
| **FBGA desconhecido** | FBGA não encontrado no banco | `_fuzzy_fbga_candidates(pn)` |
| **Prefixo desconhecido** (camada 3) | Nenhuma família bateu o prefixo | `_combined_suggestions(pn)` |

A camada 1 (banco confirmado) **não produz sugestões** — o PN foi encontrado.

`pn_incomplete=True` é setado quando o PN é mais curto que `fam.pn_length` E
a gramática não conseguiu decodificar a capacidade. Chips reconhecidos pela
família mas com sufixo ausente entram neste caso.

---

## 5. Gate de confiança — só `confirmed` e `manual`

```python
_SUGGESTION_CONFIDENCE = ("confirmed", "manual")
```

Registros `distributor` e `estimated` **nunca são sugeridos**. O operador não
deve ser direcionado a um PN cujos dados vêm de scraper ou estimativa — o
risco de mandar um chip para a bancada errada é alto demais.

Este filtro substituiu o antigo `status="enriched"` (campo removido em
jun/2026). Com o `status` fora do modelo, `confidence` é o único gate.

**Implicação prática:** para que um PN apareça como sugestão, ele precisa antes
estar confirmado via `fix_known_parts`, `populate_*`, ou aprovação manual no
admin. PNs scraped que ainda não passaram por confirmação ficam invisíveis.

---

## 6. Frontend — diff visual no chip cloud

Ao renderizar as sugestões, um script JS inline calcula o maior prefixo comum
entre o PN digitado e cada sugestão. A parte comum fica na cor padrão; a
divergência aparece em verde com um `+` ao lado.

```
Digitado: H5TQ2G83
Sugestão: H5TQ2G83CFR

Renderizado: H5TQ2G83  +CFR+
              (azul)    (verde)
```

```
Digitado: D9SGO
Sugestão: D9SGQ

Renderizado: D9SG  +Q+
              (azul) (verde)
```

O algoritmo usa prefixo mais longo — não diff completo. Se a sugestão diverge
antes do final (ex: `KMQ310006B` vs `KMQ3100068`, diferem na 9ª posição),
apenas `KMQ31000` aparece em azul e `6B` em verde.

**Por que não diff completo?** Para chips, erros ocorrem quase sempre no final
(sufixo de capacidade/temperatura) ou num único caractere isolado. O prefixo
captura ≥ 95% dos casos sem precisar de biblioteca de diff.

**Onde está:** script inline no final de `decode_card.html` (homepage HTMX) e
dentro do bloco `{% if gateway.typo.has %}` em `confirm_card.html` (estoque).
HTMX re-executa scripts em conteúdo trocado — funciona corretamente.

---

## 7. Dados do resultado JSON

```json
{
  "fuzzy_suggestions": ["D9SGQ", "D9SG0"],
  "pn_not_in_db": true,
  "pn_incomplete": false
}
```

`fuzzy_suggestions` é sempre uma lista de strings (part_numbers ou FBGA codes).
Lista vazia `[]` quando nenhuma sugestão está disponível.

No estoque, `_compute_gateway` em `estoque/views.py` transforma:

```python
gateway.typo.has         → bool(fuzzy_suggestions)
gateway.typo.suggestions → fuzzy_suggestions
```

---

## 8. Parâmetros de tuning

| Parâmetro | Onde | Valor atual | Efeito de aumentar |
|---|---|---|---|
| `threshold` | `_fuzzy_candidates` / `_fuzzy_fbga_candidates` | `2` | Mais sugestões, mais ruído |
| `min_prefix_len` | `_prefix_candidates` | `7` | Diminuir → prefixos mais curtos retornam sugestões (mais ruído) |
| **`_MAX_SUGESTOES`** | `chips/engine.py` (módulo) | **`40`** | Teto ÚNICO de prefixo + merge. Era `5` e **o 5 era o bug** (§11). Baixar volta a esconder revisão em silêncio |
| Teto da nuvem INLINE | `confirm_card*.html` (`\|slice:":5"`) | `5` | É só atalho visual; a lista COMPLETA é o popup. Subir empurra o card pra fora da tela |
| Limiar do campo de filtro | `_fuzzy_modal.html` (`length > 6`) | `6` | Abaixo disso o filtro é ruído na bancada |
| Custo no `_CHIP_VISUAL_COST` | `chips/engine.py` | vários | Diminuir = sobe na ordenação |

---

## 9. Como adicionar um novo par de confusão

1. Identifique o par (ex: `{'P', 'F'}`) e estime o custo (0.1 = quase idêntico,
   0.5 = similar, 0.9 = confusão rara).
2. Adicione ao `_CHIP_VISUAL_COST` com `frozenset`:
   ```python
   frozenset({'P', 'F'}): 0.3,
   ```
3. Teste com um PN real onde a confusão ocorre.
4. Não é necessário reiniciar o servidor — o dict é carregado em módulo.

**Critério de inclusão:** a confusão precisa ocorrer em silkscreen ou gravação
a laser de chips IC reais — não em teclados ou OCR genérico. Erros raros de
digitação não justificam entrada na matriz (aumentam ruído nos resultados).

---

## 10. Limitações conhecidas

- **PN com hífem no banco:** `SD7DP28C-4G` começa com `SD7DP28C`, então o
  prefixo funcionaria — mas o PN precisa estar no banco com `confidence=confirmed`
  ou `manual`. Se ainda é `estimated`, não aparece.
- **Sufixo no meio:** se a confusão não é no prefixo (ex: `KMQ31M006B-A` vs
  `KMQ310006B-A`), o prefixo comum para na divergência e o diff verde pode
  parecer "estranho". Isso é correto — o sistema indica onde começa a diferença.
- **Famílias sem PNs confirmados no banco:** família nova adicionada via
  `populate_*` mas sem nenhum `fix_known_parts` ainda → zero sugestões. A
  gramática classifica, mas ninguém foi confirmado para sugerir.
- **Performance em banco grande:** `_fuzzy_candidates` faz um SELECT de todos
  os part_numbers confirmados + loop Python de distância. Em produção, o
  banco confirmado é pequeno (< 10k PNs) — custo aceitável. Se crescer para
  centenas de milhares, considerar índice de trigram no Postgres.

---

## 11. Histórico de decisões

| Data | Decisão |
|---|---|
| jun/2026 | Levenshtein inteiro substituído por `_visual_edit_distance` com `_CHIP_VISUAL_COST` — resolvia D9SGO não sugerindo D9SGQ |
| jun/2026 | `_prefix_candidates` adicionado — resolvia H5TQ2G83 sem sugestão (diff de comprimento > threshold) |
| jun/2026 | UI redesenhada: chip cloud horizontal (flex-wrap), label "VOCÊ QUIS DIZER?", diff verde, sem card amarelo |
| jun/2026 | Gate `confidence__in=("confirmed","manual")` adicionado — bloqueava sugestão de PNs não confirmados (ex: KA8G16 estimated) |
| jun/2026 | `status="enriched"` removido do modelo `KnownPart`; `confidence` passou a ser o único gate de sugestão |
| **2026-08-24** | **O corte alfabético em 5 escondia revisões inteiras — o pior bug que este sistema já teve.** O operador digitou `K4B4G16`; o chip na mão era `…46E`, **aprovado no banco**; o popup mostrou 5 PNs e nenhum era `46E`. Causa: `.order_by("part_number")[:5]` — não era ranking ruim, era **ausência de ranking**. Existem 12 variantes aprovadas desse PN base e as linhagens `46B`/`46D` enchiam as 5 vagas; **toda** a linhagem `46E` era invisível, sempre, e **sem nenhum aviso de truncagem**. Efeito no negócio: o operador conclui que o chip não está no catálogo e **descarta material bom** — o oposto exato do que o fuzzy existe para fazer. Correção em três camadas: ordenação por relevância (comprimento, depois alfabético), teto único `_MAX_SUGESTOES=40`, e popup com lista completa rolável + contador + filtro (reusando `"Filtrar por PN…"`, zero msgid novo). A nuvem inline ficou em 5 por `\|slice`, como atalho. Travas: `SugestaoPrefixoRankingTests` (engine) e `PreviewFuzzyPopupMascaradoTests` (tela), validados por mutação. **Lição:** corte silencioso numa lista de sugestões é pior que lista vazia — a lista vazia o operador questiona, a truncada ele acredita. |
