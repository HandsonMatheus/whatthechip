# Briefing para o chat de Rentabilidade — o Gateway de Triagem agora deriva de vocês

> Cole isto no chat do sistema de rentabilidade. Resume um contrato novo entre
> `assess_profitability` (de vocês) e o gateway de triagem do estoque.

---

## 1. O que mudou

O **estoque** ganhou um "gateway" que decide o destino de cada chip lido na
bancada: **APROVADO / FILA / REPROVADO / DESCONHECIDO**. Esse gateway **não tem
regra de rentabilidade própria** — ele é 100% consumidor de `assess_profitability`.
A rentabilidade continua sendo a **fonte única da verdade**.

Foi adicionada **uma função derivada** no `chips/engine.py`, logo após
`assess_profitability`:

```python
def is_dead_by_generation(result: dict) -> bool:
    # remove os NÚMEROS de capacidade do result e pergunta se AINDA é NÃO RENTÁVEL
    return assess_profitability(_strip_capacity(result)) == "NÃO RENTÁVEL"
```

`_strip_capacity` apaga só os números (`"LPDDR3 1GB" → "LPDDR3"`, `"16GB" → ""`),
preservando tipo/geração/subtype.

**Ela NÃO mantém lista própria de regras.** Por isso fica **sempre em sincronia**
com vocês: qualquer regra nova que vocês criarem é refletida automaticamente.

---

## 2. O conceito: "não rentável por capacidade" vs "por geração/era"

Existem dois sabores de `NÃO RENTÁVEL`, e o gateway os trata **de formas
diferentes**:

| Sabor | Como a regra decide | Exemplos | O gateway… |
|---|---|---|---|
| **Independe da capacidade** (geração/era/tipo) | A regra dispara **sem precisar do número** de GB | LPDDR2 (gen<3), DDR2 (gen<3), MCP legado (chip_type), *futuro:* NOR/K5 | manda pro **REPROVADO mesmo SEM confirmação no banco e sem capacidade mapeada** ("reprovado por geração", com auditoria) |
| **Depende da capacidade** | A regra precisa do **número** de GB/Gb | eMMC < 4 GB, NAND < 8 GB, RAM < 1 GB, LPDDR3 < 2 GB | só REPROVA se o chip estiver **confirmado no banco**; senão vai pra **FILA** (revisão do gestor) |

**Por que a diferença?** A geração/era é lida posicionalmente da gramática curada
e "tecnologia velha = sucata" é fato de mercado — seguro descartar mesmo sem
confirmação. Já a **capacidade** vinda só de gramática pode estar errada/não
mapeada — descartar por isso sem confirmação é arriscado (poderia jogar fora algo
valioso). Decisão de negócio: **limite rígido — só geração age sem confirmação**.

**Vocês não precisam sinalizar nada.** O gateway descobre o sabor **automaticamente**
removendo a capacidade e vendo se a rejeição sobrevive.

---

## 3. O que isso implica ao escrever regras novas

1. **Sucata por classe/era** (a classe inteira não tem liquidez, independente da
   capacidade): escreva a regra olhando **só tipo/família/subtype/geração**, sem
   depender do número. Aí **confirmados E não confirmados** são corretamente
   reprovados. Ex.: a regra que já existe `chip_type.lower() == "mcp" → NÃO RENTÁVEL`.

2. **Corte por tamanho** (a peça é pequena demais): a regra depende do número →
   ela continua **exigindo confirmação** para reprovar (por design). Ex.: eMMC < 4 GB.

3. **Mantenham `assess_profitability` devolvendo só** `"RENTÁVEL"` /
   `"NÃO RENTÁVEL"` / `"INDETERMINADO"`. **Não** coloquem lógica de destino do
   estoque (caixa/aprovado/etc.) lá — o gateway cuida disso a partir dessas 3
   strings.

---

## 4. O caso que motivou este briefing (NOR / K5)

`K524G2GACJ` — Samsung **K5**, **NOR Flash / Raw MCP**, era feature phone
(~2004-2008). O engine traz `chip_type="NOR Flash"`. O `assess_profitability` **não
tem regra para NOR** → cai em `INDETERMINADO` → o gateway (regra conservadora
INDETERMINADO→aprovado) **aprova um chip que é sucata**. O próprio engine já sabe
que é lixo (campos `tip`/`device` dizem "Caixa Vermelha / moagem").

**Conserto (do lado de vocês):** uma regra **capacity-independent** —
`NOR Flash / família K5 / "Raw MCP" → NÃO RENTÁVEL`. Atenção: a regra de `"mcp"`
existente **não** pega esses (eles chegam como `"NOR Flash"`, não `"mcp"`).

Resultado automático após o conserto:

- **Confirmado** → REPROVADO (etapa normal do gateway).
- **Não confirmado** → REPROVADO por geração (atalho derivado — sem mexer no gateway).

Sem a regra: `is_dead_by_generation(K524G2GACJ) == False`. Com a regra
(capacity-independent): vira `True` sozinho.

---

## 5. Como verificar a sua regra (1 linha)

```python
from chips.engine import is_dead_by_generation
is_dead_by_generation(classify("K524G2GACJ"))  # deve virar True após a regra NOR/K5
```

Se a sua regra nova for capacity-independent e correta, `is_dead_by_generation`
passa a devolver `True` para os chips daquela classe — sem nenhuma mudança no
estoque/gateway.
