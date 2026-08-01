# PLANO_FX — câmbio RMB→USD: exibição, trava e fonte

> Plano vivo do tratamento cambial do sistema de preços. Substitui e corrige o
> `HANDOFF_fx_lock_lot_closing.md` (documento avulso de 2026-07, fora do repo),
> cujo diagnóstico central estava errado — ver §2. Contexto de negócio:
> PRECIFICACAO.md (F10: RMB canônico).

---

## 1. Decisões FECHADAS (dono, 2026-07-31)

1. **¥ é a promessa; US$ é tradução aproximada.** O front passa a exibir o
   preço em **YUAN (¥) como valor primário**, com o **US$ ao lado marcado
   como aproximado ("≈")**. Motivo: o preço-verdade do contrato com o
   comprador É em ¥ (F10 já armazena assim); o US$ é derivado por uma taxa.
   Exibir o US$ como se fosse a verdade nos deixava "reféns da flutuação"
   e com medo de mostrar valor errado pro cliente — para cima ou para
   baixo. Com o ¥ na frente, a flutuação do dólar deixa de ser um bug de
   exibição: é só a tradução que oscila, e ela está rotulada como
   aproximação.
2. **Faixa (eMCP/uMCP) valora pelo MÁXIMO.** `PricingConfig.default_scenario
   = high` (era `mid`). É configuração, não código: Admin → Pricing →
   Configuração de Preços → "Cenário padrão de faixa". Vale para valoração
   de lote, export e congelamento da OV (todos leem o mesmo default).
3. **O lock no fechamento do lote continua valendo** (acordo com o
   comprador: taxa travada quando o fornecedor fecha o lote, honrada no
   pagamento) — mas vira a Fase C, pequena, porque a exibição ¥-primeiro
   remove a urgência do "feed vivo".

## 2. Diagnóstico CORRETO do estado atual

- A taxa **não é hardcoded**: é o campo contratual **`Buyer.fx_usd_rate`**
  (hoje **0.14**), editável no admin. O handoff antigo afirmava "≈0,14
  fixo no código" — errado.
- **F10 (RMB canônico) já está no ar:** todo preço é armazenado em ¥; o
  US$ é **derivado na leitura** (¥ × taxa contratual). Lote aberto reflete
  a taxa vigente na hora; **OV confirmada já CONGELA ¥ + taxa + US$ linha
  a linha** (app vendas) — pagamento não flutua depois de confirmado.
- O "0,15" que circulava em planilhas do comprador é **histórico** — a
  taxa vigente de contrato é uma só (0.14). Toda divergência é de
  comunicação, não de sistema. 1 centésimo de taxa ≈ ±7% no lote
  (ex. real: lote de ¥63k → ±US$ 630).

## 3. Fases (revisadas — a antiga "Fase 1: feed vivo" caiu de prioridade)

- **Fase A — exibição ¥-primeiro (próxima):** bancada, página do lote,
  valoração e export passam a mostrar `¥ N (≈ US$ M)`. O catálogo do
  parceiro já é ¥-nativo; OV/fatura já são congeladas. ⚠ Tensão a decidir
  ANTES de codar: a máscara v3.1 esconde o ¥ do admin de EMPRESA (US$-only
  — o ¥ era tratado como segredo do lado-compra da plataforma). ¥-primeiro
  para o cliente reabre essa cortina. Opções: (a) ¥ vira público para o
  cliente também; (b) ¥-primeiro só para plataforma/superuser e o cliente
  segue US$-only (com "≈"). **Decisão do dono pendente.**
- **Fase B — taxa como configuração viva-o-suficiente:** manter a taxa
  contratual como campo, com atualização manual/agendada e **carimbo de
  data** visível ("taxa do contrato, atualizada em DD/MM"). Feed
  automático (API de mercado) só se/quando o contrato passar a ser
  "taxa de mercado do dia" — hoje não é.
- **Fase C — lock no FECHAR LOTE:** gravar `fx_rate` no `Lot` no momento
  do fechamento (ação física do fornecedor), exibir no modal de
  fechamento e a OV herdar essa taxa em vez da vigente na confirmação.
  Pequena: o congelamento na OV já existe; isto só antecipa o instante.
- **Fase D — integração Odoo** (fatura/pagamentos): inalterada, depois de C.

## 4. O que NÃO muda

¥ canônico no banco (F10); moderação de preços; ponto da faixa = cenário
configurável (agora `high`); acerto pós-venda continua corrigindo o valor
final real; OV confirmada permanece imutável.
