# Testes — o dólar do herói (bug GRAVE de 07/09/2026)

> "bug GRAVE encontrado, como é possivel eu ter rechazado chips e o resultado
> final em USD dar US$ 6246.12, contra US$ 6235.30 esperado? Está somando!"

## O que era

O cartão do topo da conferência mostrava **duas contas diferentes para o mesmo
fato**, uma ao lado da outra:

| | de onde vinha |
|---|---|
| **ESPERADO** US$ | `so.total_usd` — a **soma** dos `unit_usd` congelados, linha a linha |
| **RESULTADO** US$ | `pagar * fx` no JavaScript — o **total em ¥ vezes a taxa** |

A segunda é a conta que o `services.confirm` proíbe por escrito:

> Total US$ = SOMA das linhas congeladas (estilo fatura: quem confere a conta
> linha a linha tem que chegar no total) — **NÃO** `total_rmb × taxa`, que
> divergiria por arredondamento por linha.

No lote dele o grosso era DDR3 2Gb a ¥3. `¥3 × 0,1481 = 0,4443`, que congela em
**0,44**: cada unidade perde 0,0043 de dólar na soma congelada, e eram milhares
de unidades. O total em ¥ vezes a taxa saía ~**US$ 20 acima** da soma das
linhas. Recusar ¥63 de chips derrubava esse número em apenas US$ 9,33 — menos
que os 20 de vantagem que a conta errada já carregava. Na tela: **recusa que
aumenta a conta.**

⚠ O `recalcular()` roda no **carregamento**. O número já saía errado antes da
primeira tecla: o servidor escrevia 6235.30 no HTML e o script trocava por
6255.45 no mesmo instante. Numa captura anterior o herói dizia **US$ 6251.00** e
o rodapé da mesma tabela dizia **US$ 6230.82**, na mesma tela, no mesmo segundo.

## O que NÃO era

Varredura completa: **nenhum valor gravado** usava a conta errada. Era só a
tela. Conferido um por um:

| ponto | conta | veredito |
|---|---|---|
| `services.confirm` → `so.total_usd` | soma dos `unit_usd` congelados | ✅ |
| `services.settlement_totals` → fatura | `(unit × taxa)` por linha × qtd, somado | ✅ |
| `services.result_rows` → tabela e faixas | `unit_usd × aceitos` | ✅ |
| `_monta_documento` → PDF | `line.unit_usd` congelado (derivado só na linha **repactuada**, documentado) | ✅ |
| `planilha.py` → XLSX | `SUMPRODUCT(aceitos × unit_usd)` sobre a coluna escondida | ✅ |
| rodapé da tabela (`t-pagar-usd`) | `pagarUsd`, somado linha a linha | ✅ |
| **herói (`k-usd`)** | **`pagar × fx`** | ❌ **era o bug** |
| `_rmb_de` e a caixa de pagamento | US$ → ¥ (**divide**), leitura derivada declarada §2.4 | ✅ |
| `pricing/*` | converte **preço unitário**, não total | ✅ |

## Por que passou pelos testes

`tests_par_de_moedas` cobrava a conta certa com `assertIn`:

```python
def test_o_js_le_o_usd_congelado_e_nao_multiplica_pela_taxa(self):
    self.assertIn('i.dataset.unitUsd', self.js)
    self.assertIn('valUsd = ok * unitUsd', self.js)
```

Tudo verdade — e tudo continuava verdade com o `pagar * fx` cinco linhas
abaixo. **Regra do tipo "NUNCA faça X" não se prova mostrando que Y existe.**

## Testes automatizados

```bash
python manage.py test vendas.tests_dolar_do_heroi
```

18 testes. Os 14 primeiros são leitura estática e rodam em qualquer máquina;
os 4 últimos (`NavegadorTests`) carregam a ficha num DOM de verdade, deixam o
script da página rodar, digitam a recusa e **leem o número na tela**.

**Provados contra o bug**: com a correção desfeita, 5 estáticos e os 4 de
navegador reprovam — inclusive com a frase dele:
`recusar chips AUMENTOU o resultado em US$`.

### Os de navegador precisam de `jsdom`

Não é dependência do projeto (exigir node de quem só quer subir o servidor
seria trocar um teste por um obstáculo). Sem ele a classe **pula sozinha** e o
portão continua sendo o estático.

```bash
npm install jsdom          # na raiz do projeto, cria node_modules/
# ou:  NODE_PATH=/caminho/para/node_modules python manage.py test vendas.tests_dolar_do_heroi
```

O harness é `vendas/tests_js/heroi.mjs` e pode ser rodado à mão:

```bash
NODE_PATH=./node_modules node vendas/tests_js/heroi.mjs ficha.html '{"12": 50}'
# → {"antes":{"kUsd":"US$ 4400.00", ...},"depois":{...},"digitou":1,"campos":1}
```

## Testes de interface (na tela, manual)

Numa OV **confirmada e recebida**, com o comprador logado, aba **Conferência**.

Pré-requisito para o teste valer: o lote precisa ter um unitário em que as duas
contas divirjam — **¥3,00 com taxa 0,1481** é o caso real (congela em 0,44;
¥3 × 0,1481 = 0,4443). Com um unitário "redondo" os dois números batem e o teste
não prova nada.

| # | passo | o que TEM de acontecer | o que era o bug |
|---|---|---|---|
| 1 | Abrir a ficha, **sem digitar nada** | O US$ de **RESULTADO ESPERADO** e o de **RESULTADO FINAL** são **idênticos** | o FINAL nascia maior |
| 2 | Ainda sem digitar, olhar o **rodapé** da tabela | O `RESULTADO` do rodapé é **igual** ao do cartão | discordavam na mesma tela |
| 3 | Digitar **1** recusa numa linha | O US$ do FINAL **cai** | subia, ou caía menos que devia |
| 4 | Apagar a recusa (campo vazio) | O US$ volta **exatamente** ao esperado | voltava para o número inflado |
| 5 | Recusar **o lote inteiro** | `US$ 0.00` e `¥ 0.00` — **zero escrito como número**, não travessão | — |
| 6 | Com recusa digitada, baixar **RESULTADO PARCIAL** | O total em US$ do PDF é **o mesmo** que está na tela | tela e papel divergiam |
| 7 | Exportar o **XLSX** | O `RESULTADO` do cabeçalho é **o mesmo** que está na tela | idem |
| 8 | **Fechar resultado** e recarregar | O FINAL da fatura é **o mesmo** número que a tela mostrava antes de fechar | o número "pulava" ao recarregar |

Passos 6, 7 e 8 são o que mais importa: é onde a divergência sairia do navegador
e viraria **papel na mão do cliente**.

### No celular (≤600px)

| # | passo | o que TEM de acontecer |
|---|---|---|
| 9 | Abrir a conferência no telefone | A barra viva do rodapé mostra `¥` — ela é só ¥ de propósito, e não tem US$ para divergir |
| 10 | Digitar recusa | O cartão do topo cai em US$ **e** em ¥, juntos |

## A regra, para a próxima vez

> **US$ nunca sai de um TOTAL em ¥ vezes a taxa.** Sai da soma dos `unit_usd`
> congelados, linha a linha. Vale em Python, em JavaScript, no PDF e na
> planilha. O caminho inverso (US$ → ¥, **dividindo**) é leitura derivada
> declarada da §2.4 e continua permitido — é o que o `_rmb_de` e a caixa de
> pagamento fazem.

E o teste dessa regra é `assertNotIn` + **rodar a tela**, nunca `assertIn` de
outra coisa.
