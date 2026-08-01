# PLANO_FX — câmbio RMB→USD: mercado vivo, trava no fechamento, ¥ primário

> Plano vivo do tratamento cambial do sistema de preços. Substitui o
> `HANDOFF_fx_lock_lot_closing.md` (doc avulso, fora do repo) — cujo
> diagnóstico técnico estava errado (§3) mas cujo MODELO DE NEGÓCIO o dono
> confirmou (§1.1). Decisões fechadas em 2026-07-31. Contexto: PRECIFICACAO.md
> (F10: RMB canônico). **Execução: pacote PRÓPRIO, depois do push da
> repactuação — nada disto está codado ainda.**

---

## 1. DECISÕES FECHADAS (dono, 2026-07-31)

1. **O acordo com o comprador é taxa de MERCADO no instante do fechamento
   do lote.** Logo: lote ABERTO tem o US$ atualizando com o câmbio
   (¥ sempre fixo pela tabela); FECHAR trava a taxa daquele momento; OV,
   fatura, pagamento do comprador **e o repasse ao fornecedor** usam a
   taxa travada do lote (risco cambial zerado no meio da cadeia).
2. **A taxa contratual `Buyer.fx_usd_rate` (0.14) MORRE de vez.** Toda
   conversão passa a ser mercado — viva no aberto, travada no fechado.
   Histórico não se mexe: lotes/OVs já congelados a 0.14 ficam como estão.
3. **Fechou, tá fechado.** Reabertura de lote é REMOVIDA do produto para
   todos — exceto o **superuser Django** (plataforma = o dono), auditada.
   Lote reaberto volta ao câmbio VIVO; re-fechar captura taxa NOVA; as
   duas travas ficam logadas. Correção pós-fechamento para todo o resto do
   mundo = **Acerto** (padrão Odoo: ordem intocada + ajuste vinculado).
   Barreira anti-acidente do fechamento continua: digitar o código do lote.
4. **Exibição ¥-primeiro em todo o front** — `¥ N (≈ US$ M)` — inclusive
   para a empresa-CLIENTE (máscara v3.1 revista: o ¥ deixa de ser oculto;
   opção (a) do dono). No lote aberto o "≈ US$" é vivo e rotulado como
   não-travado; no fechado vira o selo da trava (§5 Fase C).
5. **Fonte da taxa: mid-market interbancária, referência DIÁRIA** (a "mais
   usada do mundo" — a que Google/XE/Wise mostram). Trava-se a referência
   DO DIA do fechamento, não o tick do minuto: um número por dia é
   verificável pelos dois lados (mata disputa); o intradia do CNY é banda
   administrada ±2% — centavos. Transporte: API gratuita estável (ex.
   open.er-api.com, já usada no projeto), atualização diária + fallback
   última conhecida (`fx_is_fallback`) + histórico carimbado. ⚠ PENDENTE
   DE NEGÓCIO: alinhar a referência com o comprador (balão de WeChat) —
   a fonte é cláusula, não detalhe.
6. **Faixa (eMCP/uMCP) valora pelo MÁXIMO** — `PricingConfig.
   default_scenario = high` (flip no admin, local e prod; config, não
   código).
7. **Arredondamento:** taxa com 4 casas; US$ com 2 (HALF_UP); ¥ inteiro
   na exibição. (Padrão fechado por ausência de objeção.)

## 2. O modelo em uma linha

**¥ é a promessa (tabela, fixo) · US$ é tradução de mercado (vivo → ≈;
fechado → travado e imutável) · uma taxa por lote, verificável, que rege
todos os pagamentos daquele lote nas duas pontas.**

## 3. Diagnóstico correto (herança do handoff, corrigido)

- A taxa NÃO era hardcoded: era o campo contratual `Buyer.fx_usd_rate`
  (0.14) — que agora morre (§1.2). O "0,15" das planilhas era resquício
  histórico; a divergência morre junto.
- F10 já deixou tudo pronto para isto: preço armazenado em ¥; US$ derivado
  na leitura; OV congela ¥+taxa+US$ na confirmação. O que muda é DE ONDE a
  taxa vem (mercado, não contrato) e QUANDO trava (fechamento do lote, não
  confirmação da OV — a OV passa a HERDAR a taxa do lote).
- 1 centésimo de taxa ≈ ±7% do lote (ex. real: lote de ¥63k → ±US$ 630) —
  maior que a margem de vários tipos; por isso a trava é vital.

## 4. Fases de execução — **A, B e C ENTREGUES local (2026-08-01)**

> Fase C: `Lot.fx_rate/fx_source/fx_locked_at/fx_is_fallback` + pghistory
> no Lot (cada trava/retrava é evento auditável). `lot_close` captura a
> taxa vigente ATÔMICO com o CLOSED (sem taxa no sistema NUNCA bloqueia o
> fechamento — campos nulos + aviso); modal mostra "Câmbio que será
> TRAVADO agora: 1 ¥ = US$ X (mid-market DD/MM)" antes do confirmar
> (requisito explícito); selo 🔒 no lote fechado (todas os papéis — taxa é
> dado público). **Fechou, tá fechado**: reabrir é EXCLUSIVO do superuser
> (gate no servidor + botão some; demais veem "correções = acerto");
> reabertura DESTRAVA (campos limpos, histórico no pghistory) e re-fechar
> captura taxa nova. OV: `confirm()` herda `lot.fx_rate` (mercado-na-
> confirmação só p/ lote legado sem trava); rascunho exibe a travada.
> `FxLockOnCloseTests` (4 — incl. mercado mudando após a trava e a OV
> mantendo a travada: ¥20 × 0.1478 = US$ 2.96).

> Fase A: card da bancada/busca ¥-PRIMEIRO (`¥ 40` grande + `≈ US$ 5.60` +
> carimbo "taxa mid-market DD/MM"); máscara v3.1 revogada (cliente vê ¥ —
> opção (a)); valoração/cards de lote `¥ N ≈ US$ M`; export com coluna
> "Preço unit. (¥ RMB)" antes do "US$ ≈"; header do parceiro com taxa viva
> carimbada. Fase B: modelo `FxRate` (1 linha/dia, fonte, is_fallback,
> histórico; GLOBAL) + `fetch_fx_rate` (er-api via urllib, idempotente,
> fallback repete última com ⚠) + `current_fx_rate()` fonte única no engine
> (mercado → bootstrap contratual só com a tabela vazia) — consumida por
> quote/contexto (cacheada 1×/lote), SSD, catálogo PDF, vendas
> (rascunho + congelamento na confirmação). `FxRateTests` (4) + flips de
> máscara/header/export. Falta: agendar o fetch (Render Cron, 1×/dia).

- **Fase A — exibição ¥-primeiro:** bancada, página do lote, valoração,
  export: `¥ N (≈ US$ M)`; máscara v3.1 revista (¥ visível ao cliente);
  aberto rotulado "≈ taxa de DD/MM, não travada".
- **Fase B — serviço de câmbio:** modelo `FxRate` (data, taxa, fonte,
  is_fallback) + fetch diário agendado + fallback + histórico auditável;
  ponto ÚNICO de leitura para todo o sistema; aposentadoria do
  `Buyer.fx_usd_rate` (migração remove o uso; valores históricos
  congelados intactos).
- **Fase C — trava no FECHAR LOTE:** campos imutáveis no `Lot`
  (`fx_rate`, `fx_source`, `fx_locked_at` UTC, `fx_is_fallback`);
  captura ATÔMICA na transação do fechamento; modal mostra a taxa e o
  US$ resultante ANTES do confirmar (requisito explícito); selo
  "Câmbio travado: X em DD/MM" no lote fechado; OV herda a taxa do lote;
  reabertura só-superuser com re-trava logada (§1.3). Fonte indisponível
  NÃO bloqueia o fechamento físico: usa fallback + flag + alerta.
- **Fase D — Odoo:** fatura/venda do lote no Odoo usa a taxa travada
  (empurrar USD fixado ou setar a taxa da fatura); gravar a taxa no
  registro Odoo para reconciliação.

## 5. Fora da engenharia (lembretes)

- **Contador:** variação cambial (trava hoje, recebe depois) tem
  tratamento contábil/fiscal próprio no Paraguai — validar o lançamento.
- **WeChat:** propor ao comprador a referência mid-market diária como
  cláusula (balão pronto sob demanda).
