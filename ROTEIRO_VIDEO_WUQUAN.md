# Roteiro do vídeo para o Wu Quan — “como dar o resultado de uma compra”

> **O que é.** Roteiro de gravação de tela + legendas em mandarim para o
> tutorial que ensina o comprador a **fechar o resultado** de um lote no painel
> do parceiro. Documento de trabalho do dono: leia inteiro **antes** de apertar
> o REC — tem três armadilhas que só aparecem na hora, e uma delas emite uma
> fatura de verdade.
>
> Fluxo coberto: `标记为已收货` → `核对` → `拒收` por linha → `结算` → PDF do
> resultado → `付款记录`.
> Código de referência: `vendas/views_partner.py::compra_recebido`,
> `::compra_resultado`, `vendas/templates/vendas/partner_compra.html`,
> `locale/zh_Hans/LC_MESSAGES/django.po`.

---

## 1. A decisão: legenda, não dublagem

Descartada a ideia de gravar falando em português e dublar para mandarim, por
três motivos:

1. **A fala é a metade menor do problema.** Dublar a voz não traduz os botões.
   Ele ouviria mandarim e continuaria vendo uma tela que não sabe ler.
2. **Dublagem automática destrói o vocabulário da casa** — `eMCP`, `LPDDR4`,
   `LOT-2026-00xx`, `EMIN-SO-2026-00xx`, valores em ¥. É o pior caso possível
   para essas ferramentas.
3. **O WTC já fala `zh-hans`** na interface inteira desde 2026-07-08, painel do
   comprador incluído (`MULTILANGUAGE.md` §1). O vídeo nasce em mandarim de
   graça — basta trocar o idioma antes de gravar.

**Consequência prática:** grava-se **em silêncio**, com a interface em 中文, e
as legendas em mandarim são queimadas depois. Elas citam cada botão com a
**grafia idêntica à da tela dele** — o texto do `zh_Hans/django.po`, não uma
tradução nova.

---

## 2. ⚠️ Antes de gravar: o acesso (resolver isto primeiro)

`partner_required` (`pricing/views.py:77`) exige que o usuário logado esteja
vinculado a um `Buyer` ativo via `Buyer.users`. **Ser staff ou superuser não
passa pelo portão.** Não dá para “ver como o Wu Quan” a partir da sua conta.

E o gate resolve o vínculo com `.first()` (v1: o primeiro) — então **não**
adicione a sua conta ao `Buyer` dele: se você já estiver vinculado a outro
comprador, o painel pode continuar mostrando o outro.

**Faça assim:** no admin, crie um usuário novo e dedicado (ex.: `demo.zh`),
vincule **só** ao `Buyer` do Wu Quan, grave, e desvincule depois. Sem pedir
senha a ninguém.

### E a fatura de verdade?

`compra_resultado` é atômico: ao confirmar, ele **cria o acerto e emite a
fatura**, e a própria tela avisa que os números não mudam mais. Clicar `结算`
numa OV real do Wu Quan durante a gravação **fatura o lote de verdade**.

Dois caminhos, em ordem de preferência:

| | Como | Custo |
|---|---|---|
| **A — instância local** | Rodar o `manage.py` local com cópia do banco e gravar o fluxo inteiro sem medo. | Precisa da instância de pé; é o caminho limpo. |
| **B — corte de montagem** | Gravar a OV real **até o diálogo de confirmação** e clicar `返回修改`. Depois filmar o PDF e a aba de pagamentos de uma OV **já fechada** dele. Eu emendo os dois. | Zero risco em produção, e continua sendo dado real dele. |

Se for o **B**, me avise: o corte entre a cena 09 e a 10 tem de ser disfarçado,
e isso muda como eu monto.

---

## 3. Ajustes de tela (2 minutos, valem o vídeo inteiro)

O destino é o **WeChat, no celular**. O WeChat recomprime vídeo com força: o
que já está pequeno vira borrão.

- **Zoom do navegador em 150%.** Não é exagero — é o que torna a tabela legível
  num celular depois da recompressão.
- Janela do Chrome em **1280×800**, ou tela cheia em 1920×1080 que eu recorto.
- **Esconder** barra de favoritos, abas extras e extensões. Ativar **Não
  Perturbe** (notificação na tela = regravar tudo).
- **Sem áudio.** Nem microfone, nem som do sistema.
- **Cursor lento e deliberado.** Parar ~2s em cima do elemento *antes* de clicar
  — a legenda precisa de tempo para ser lida em cima daquele quadro.
- macOS: `⌘⇧5` → Gravar Porção Selecionada. Não use ferramenta que grave webcam.
- **Trocar o idioma antes de começar**, na gaveta de perfil (o `shell.js`
  transforma o seletor em quatro botões lá dentro).

Alvo: **2 a 2min30**. Acima disso ninguém termina.

---

## 4. O roteiro, cena a cena

`【】` marca botão, como manda a convenção chinesa. As legendas abaixo são as
que eu vou queimar no vídeo — a coluna PT é só para você conferir o sentido.

| # | O que fazer na tela | ~s | Legenda 中文 | Sentido (PT) |
|---|---|---|---|---|
| **00** | Cartela de abertura (eu gero, você não grava) | 3 | **如何提交验收结果**<br>WhatTheChip 采购平台 · 操作演示 | Como enviar o resultado da conferência |
| **01** | Abrir a gaveta de perfil, mostrar os 4 botões de idioma, clicar 中文 | 6 | 如果界面不是中文：打开右上角的账户抽屉，选择 中文。 | Se a interface não estiver em chinês, troque aqui |
| **02** | Menu 采购. Mostrar a lista e o código do lote | 8 | 登录后打开【采购】列表，按批次号找到本次采购。 | Entre em Compras e ache pelo código do lote |
| **03** | Passar sobre os filtros de status: 运输中 / 核对 | 7 | 状态显示【核对】时，即可开始验收。<br>（【运输中】= 货物仍在途中） | “Conferência” = pode começar; “Em trânsito” = ainda chegando |
| **04** | Abrir a compra. Clicar 【标记为已收货】 | 7 | 收到货后，先点击【标记为已收货】。 | Ao receber a caixa, marque como recebido primeiro |
| **05** | Aba 汇总: a tabela de conferência agrupada por marca | 9 | 核对表按【品牌】分组，逐行列出型号、容量和【已发】数量。 | A tabela é agrupada por marca; cada linha traz tipo, capacidade e enviados |
| **06** | **Parar.** Cartela sobre a coluna 拒收 | 6 | ⚠️ 只填写【拒收】数量 — 不是接收数量。<br>留空 = 0 = 全部接收。 | **Digita-se o RECUSADO, não o aprovado. Vazio = 0 = tudo aprovado** |
| **07** | Digitar uma recusa numa linha. Mostrar 已接收 e ¥ recalculando | 9 | 输入拒收数量后，【已接收】和 ¥ 金额会自动重算。 | Ao digitar, aprovados e valor recalculam sozinhos |
| **08** | Clicar 【清除拒收】, mostrar tudo zerando | 6 | 填错了不要紧：点【清除拒收】即可全部清空，重新填写。 | Errou? Limpa tudo e recomeça |
| **09** | Clicar 【结算】. O diálogo abre com o aviso e o 备注 | 10 | 确认无误后点【结算】。<br>【备注（可选）】可填写拒收原因、封条号等。<br>⚠️ 一经确认，数字将无法再更改 — 需修改请点【返回修改】。 | Confirme; a observação é opcional; **depois de fechar não muda mais** |
| **10** | O PDF do resultado abrindo sozinho | 9 | 结算完成后，结果单 PDF 会自动打开 — 可直接转发给您的客户。 | O PDF abre sozinho e é o documento que ele manda pro cliente dele |
| **11** | A aba 付款记录, agora destravada | 7 | 同时【付款记录】页解锁，发票已开具。 | Pagamentos destrava e a fatura foi emitida |
| **12** | Cartela de fecho (eu gero) | 4 | 如有疑问，请随时联系我们。 | Qualquer dúvida, fale conosco |

---

## 5. As três armadilhas

1. **`拒收` é recusado, não aprovado.** `compra_resultado` lê `rej_<pk>` e trata
   branco como zero — quem abrir a tela sem instrução vai digitar o aprovado e
   zerar o lote inteiro por engano. É por isso que a cena 06 é uma cartela
   parada, e não uma legenda de passagem.
2. **`结算` é irreversível.** Cria acerto + fatura num bloco atômico. Ver §2.
3. **O PDF é o prêmio, não um detalhe.** A cena 10 é o argumento de por que ele
   deve lançar no sistema em vez de mandar os números por mensagem: ele sai da
   tela com o documento pronto para o cliente **dele**. Se o vídeo tiver um
   motivo para ele mudar de hábito, é esse — não corte essa cena para encurtar.

---

## 6. Depois de gravar

Me manda o arquivo bruto, sem editar e sem cortar. Eu faço:

- corte e ritmo (incluindo a emenda do caminho **B**, se for o caso);
- legendas em mandarim **queimadas** (Noto Sans CJK), cartelas 00, 06 e 12;
- destaque visual na coluna `拒收` no momento da cena 06;
- MP4 final em tamanho que passa no WeChat;
- e o **图文教程** — o guia de uma página em chinês, com os prints numerados
  tirados do próprio vídeo, que é o que ele vai reconsultar na segunda compra.

Só não consigo gerar **locução** em mandarim: os serviços de TTS estão fora do
allowlist de rede dos dois ambientes. Se você quiser voz, o roteiro da coluna
中文 já serve de script — o macOS tem voz chinesa nativa e o CapCut/剪映 gera
de graça. Minha opinião: não faz falta. Tutorial mandado por WeChat é assistido
no mudo.
