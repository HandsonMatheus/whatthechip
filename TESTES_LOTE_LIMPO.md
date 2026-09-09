# Corrida do lote limpo — aceitação ponta a ponta

> "eu vou fechar e passar por todas as etapas, no final tentarei mudar de preço
> e gerar novamente pra ver como se comporta esta feature." — dono, 09/09/2026

Um lote novo, do zero até o pagamento, e no fim a **repactuação de preço**.
Existe uma versão desta lista com caixas de marcar (artifact "Protocolo do Lote
Limpo"); este arquivo é o registro, e é onde estão os fatos do ciclo de vida que
custaram uma leitura de código para descobrir.

## No terminal

```bash
# a migração do rascunho de preço — a 0025 guarda o preço repactuado
python manage.py migrate

python manage.py test vendas.tests_repactuacao                  #  38
python manage.py test vendas.tests_repactuacao_situacoes         #  44
python manage.py test vendas.tests_dolar_do_heroi                #  21
python manage.py test vendas.tests_medidas_do_design_system \
                      vendas.tests_cor_da_linha_que_soma \
                      vendas.tests_par_de_moedas                 #  57
python manage.py test vendas.tests_pdf_resultado \
                      vendas.tests_planilha_da_compra            #  96
python manage.py test vendas                                     # 868
```

**256** no recorte da feature, **868** no app inteiro — conferidos em 09/09/2026.

⚠ Os 8 testes que rodam o JavaScript da ficha num DOM precisam de `npm install
jsdom` na raiz. Sem ele a classe `NavegadorTests` **pula sozinha**: a saída diz
`(skipped=8)` e não falha, o que é exatamente o jeito de não perceber que eles
não rodaram.

## O ciclo de vida, como ele é de verdade

Três coisas que não estão onde a intuição procura — e as três já custaram tempo:

### 1. A ordem de venda nasce dentro do "Fechar lote"

Não existe tela que crie a OV nem que escolha o comprador. `estoque:lot_close`
chama `services.create_draft_for_lot`, que exige **exatamente um** `Buyer` com
`active=True` (`vendas/services.py:41-47`). Com zero ou dois, o lote fecha e a
OV **não** é criada — só um aviso amarelo na ficha (`estoque/views.py:1012`).

Conferir `/admin/pricing/buyer/` antes de fechar. Reparo:

```bash
python manage.py criar_ov_faltante --company <slug> --lot <n> --commit
```

### 2. Quem congela o preço é o DESPACHO

`vendas:so_confirm` existe e **não tem botão em nenhum template** — foi tirado
de propósito (comentário em `so_detail.html:355-365`). Na prática o congelamento
é efeito colateral do `mark_shipped`: no primeiro despacho, se a OV ainda é
rascunho, ele chama `confirm()` (`vendas/services.py:2254-2256`).

E se alguma linha estiver sem preço ele **engole o erro** (services.py:2257-2259):
a OV fica *rascunho-mas-despachada*, a conferência nunca abre e o lápis nunca
aparece. Por isso o preço tem de estar resolvido **antes** do despacho.

O outro caminho é automático: aprovar a cotação que faltava no `/admin/` dispara
`freeze_pending_orders` (`pricing/models.py:895`), que só mexe em OV **já
despachada** (services.py:214-216).

### 3. Enviar a cotação não aplica o preço

O grid do comprador (`/partner/tipo/<kind>/` → **Enviar para revisão**) cria um
`PriceChangeRequest` com `review_status=PENDING` (`pricing/views.py:815-823`).
É a **aprovação por um admin da plataforma** no `/admin/` que aplica o preço e
solta a OV travada.

## As etapas, em ordem

| # | quem | onde | o quê |
|---|---|---|---|
| 1 | gerente | `/estoque/` | **Novo lote** → origem (obrigatória) → **Criar e abrir** |
| 2 | operador | ficha do lote | PN no campo → **+ Adicionar ao estoque**. **Duas marcas**, duas capacidades |
| 3 | gerente | ficha do lote | **Fechar lote** → código completo digitado → **Confirmar fechamento**. *A OV nasce aqui* |
| 4 | comprador + admin | `/partner/precos/` → `/admin/` | cotar o que falta → **Enviar para revisão** → aprovar |
| 5 | gerente | `/vendas/<pk>/` | **Registrar despacho**. *Isto congela os unitários* |
| 6 | comprador | `/partner/compras/<pk>/` | **Marcar como recebido** → abre a Conferência |
| 7 | comprador | Conferência | passar o mouse: **nada muda de cor** |
| 8 | comprador | Conferência | UNITÁRIO ¥ parado: número + lápis apagado, **nenhuma caixa** |
| 9 | comprador | Conferência | recusar unidades: `−¥` na perda, RESULTADO cai, **ESPERADO parado** |
| 10 | comprador | Conferência | baixar um preço: **↓ vermelha** + antigo **riscado em vermelho** |
| 11 | comprador | Conferência | subir na outra marca: **↑ verde** + riscado **verde** |
| 12 | comprador | Conferência | desfazer: `Esc` volta · apagar volta ao congelado (seta e riscado somem juntos) · valor igual não acende nada |
| 13 | comprador | Conferência | esperar **"Salvo HH:MM"** e `F5`: tudo continua, **antes** de qualquer tecla |
| 14 | comprador | Conferência | **Resultado parcial**: `US$ x.xx ↓`, ¥ novo, ¥ antigo riscado. Gerar 2× — não grava nada |
| 15 | comprador | Conferência | **Exportar**: UNITÁRIO = novo · ESPERADO = congelado · RESULTADO = tela |
| 16 | comprador | Conferência | **Fechar resultado** → "fatura emitida", o PDF final abre |
| 17 | comprador | PDF final | a seta e o riscado estão lá, e a data de fechamento preenchida |
| 18 | comprador | ficha, após `F5` | o **lápis some**, a **seta fica**, o número é o repactuado |
| 19 | gerente | superfície do cliente | preço novo no RESULTADO, combinado no ESPERADO |
| 20 | comprador | ficha | **Registrar pagamento** (comprovante obrigatório) → parcial, depois quitação |

## A repactuação depois do fechamento

`can_settle` fica falso assim que existe fatura não-cancelada
(`vendas/services.py:1742-1744`), e `settle_and_invoice` recusa com *"Esta OV já
tem fatura ativa — cancele-a"* (services.py:811-812). Então:

- **Antes de fechar** — mudar o preço e gerar o parcial funciona quantas vezes
  quiser. O `result_preview` **não persiste nada** (services.py:630-633).
- **Depois de fechar** — o lápis não existe mais. Caminho de volta: como
  **admin**, `/vendas/fatura/<pk>/` → **Cancelar fatura** (só sem pagamentos,
  `vendas/views.py:380`).

⚠ E a conferência reabre **LIMPA**. O `result_rows` só lê o rascunho quando não
há fatura ativa (services.py:1942-1944), e o `clear_draft` do fechamento já o
apagou: recusas, setas e riscados somem, e é tudo digitado de novo. A
repactuação antiga sobrevive apenas dentro do acerto da fatura cancelada.

## O PDF sem a seta não é bug de desenho

A Helvetica do reportlab não tem `↑↓` no vetor WinAnsi. Quem os tem é a
`vendas/assets/IBMPlexMono-SemiBold.ttf` (conferido no cmap). Se ela não subiu
no deploy, `_mono_font()` cai em `Courier-Bold`, `_TEM_SETA` fica falso e **a
seta some — o preço riscado fica**. Conferir o arquivo no servidor antes de
procurar bug no `P_unit`.
