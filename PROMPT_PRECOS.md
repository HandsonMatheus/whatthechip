# PROMPT — Sessão nova: construir o sistema de PREÇOS do WhatTheChip

> Cole o texto abaixo numa sessão nova e anexe: (1) `wuquan_prices_updated_EN.xlsx` (tabela de
> preços do comprador) e (2) a planilha do lote a precificar (quando for o caso).
> Começa **só com brainstorm** — implementa depois.

---

**Contexto — vou construir o sistema de PREÇOS do WhatTheChip.**

O WhatTheChip é um app Django que classifica Part Numbers de chips de memória pro mercado de
reciclagem (eMiner, Paraguai). O classificador já devolve, pra cada chip, specs normalizadas e
**compartilhadas entre marcas**: `chip_type`, `subtype`, `capacity`, `emcp_nand`, `emcp_ram`,
`dram_density`. Quero uma **camada de preços** por cima: dado um chip classificado (ou um LOTE
inteiro), dizer quanto o comprador paga — implementando exatamente as regras da tabela do comprador.

**Onde encaixa na arquitetura:** o preço é um **lookup brand-agnostic** sobre a saída normalizada do
classificador, na mesma filosofia de fonte-única do `assess_profitability` (`chips/engine.py`): uma
camada só, config editável no admin (como o `ProfitabilityConfig`), testável e reversível. A tabela do
comprador vira um **modelo no banco** (importado do Excel, editável) + uma função `price(result)`.

**Insumos (anexos):** (1) `wuquan_prices_updated_EN.xlsx` — tabela de preços de COMPRA do comprador
(Wuquan), em inglês; (2) a planilha do lote a precificar (quando for o caso).

---

## REGRAS DE PRECIFICAÇÃO (do comprador) — o sistema deve encodar

Não invente preço; o que não tiver na tabela fica sem preço.

**1. Estrutura da tabela:** uma aba por marca (Samsung, SK Hynix, Micron, Kingston, Toshiba Kioxia,
SanDisk, Nanya, Other Brands) + aba `Instructions` (regras do comprador). Colunas: A=Brand · B=Type ·
C=Subtype · D=Capacity · E=Price(USD) · **F=★Price(RMB)** · G=Quote date · H=Source · I=Notes. **O
preço-fonte da planilha é a coluna F (RMB)** — número (`10`), faixa (`90-110`) ou `NO`/vazio (sem
preço). Câmbio na célula **B2** (hoje 0,15): **USD = RMB × 0,15** (calcule você mesmo, principalmente
nas faixas). ⚠ Ver Feature 4: o SISTEMA armazena em USD.

**2. Capacidade por tipo:**
- **eMMC / UFS** → GB (4/8/…/512GB, 1TB). Casa direto.
- **eMCP / uMCP** → na tabela a capacidade é `armazenamento+RAM` (`64+4`); no lote/classificador vem
  como `eMMC 5.1 64GB / LPDDR4X 4GB`. **Precifique pela FAIXA DE ARMAZENAMENTO (8/16/32/64/128/256GB)
  + subtipo LPDDR.** O comprador cota por faixa — todo eMCP 64GB custa igual, seja +3 ou +4 de RAM.
  Subtipo exato ausente na faixa → use qualquer subtipo da mesma faixa.
  **⚠ Implicação técnica: pro PREÇO importam o `emcp_nand` (faixa de armazenamento) e o `subtype`
  (geração LPDDR) — NÃO a capacidade exata do RAM. RAM 3 vs 4GB não muda preço; mas o subtipo
  LPDDR3/4X/5 e a faixa de NAND, sim.**
- **LPDDR avulso** (3/4/4X/5/5X) → GB, casa por subtipo + GB.
- **DDR** (3/3L/4/5) → densidade em **Gb** (`2G/4G/8G/16G`). Se vier em bytes, ×8: 256MB=2Gb,
  512MB=4Gb, 1GB=8Gb. Casa por subtipo + Gb.
- **GDDR** → normalmente `NO` (comprador não compra) → sem preço.

**3. Faixas** (`90-110`): baixo=início · médio=meio · alto=fim. Diga qual usou. Preço único → iguais.

**4. Regra por marca (qual aba):** marca com aba própria → usa a dela (a aba SK Hynix está com os
preços da Samsung — são iguais). Marca SEM aba (Rayson, PieceMakers, GigaDevice, ESMT, Winbond,
ISSI…): (a) primeiro `Other Brands` (linha marca+tipo+capacidade batendo — ex.: Rayson eMMC 8GB);
(b) senão, **Nanya como CURINGA** — mas a Nanya só cobre LPDDR4 e DDR, então marca desconhecida com
eMMC/eMCP/UFS/uMCP fora do `Other Brands` fica sem preço.

**5. Fica SEM preço:** coluna F vazia/`NO`; LPDDR5/5X ou GDDR não cotados; capacidade inexistente na
tabela da marca; marca desconhecida sem cobertura. Deixa em branco + anota o motivo — **nunca chuta**.

**6. Saída (precificando lote):** por linha → unitário USD, total (× qtd). No fim → total geral USD;
**cobertura** (% de unidades e % de linhas com preço); lista do sem-preço com motivo; se houver faixa,
total no cenário escolhido (baixo/médio/alto).

---

## FEATURES OBRIGATÓRIAS (do dono)

1. **Duas telas de edição de preço:** (a) **Django admin** — pro administrador do SaaS; (b) **dashboard
   do comprador** — o comprador (Wuquan) também edita de lá (front próprio, fora do admin). Os dois
   escrevem na MESMA fonte (o modelo de preços no banco).
2. **`last_updated` em todo preço** — atualizado automaticamente sempre que alguém troca o valor.
3. **`updated_by` interno** — o sistema registra QUAL usuário trocou cada preço. **No frontend
   (dashboard do comprador) NÃO mostra** nem `updated_by` nem `last_updated` — só aparecem no
   **backend/admin**. Auditoria interna, invisível pro comprador.
4. **Moeda canônica = USD.** Preços definidos e armazenados em **dólar** (convenção única). O import da
   planilha (RMB) converte RMB→USD (× câmbio); daí em diante admin e comprador editam em USD, e o
   RMB/câmbio vira só referência de importação, não fonte viva.
5. **Verificar a convenção dos PNs ANTES de confiar no preço.** O preço depende de casar (marca, tipo,
   subtipo, faixa de capacidade). Verificar se a convenção de classificação (`chip_type`/`subtype`/
   `emcp_nand`/`capacity` — fonte em `chips/chip_types.py`) é sólida e consistente o bastante pra keyar
   preço de forma escalável. Buracos (subtipo inconsistente, os known_parts identity-only do
   `PLANO_QUALIDADE_DADOS.md`) entram no plano — preço em cima de spec frouxa não escala.

---

## CONTEXTO CRÍTICO DE SEGURANÇA

- **Regra de ouro #1:** o agente EDITA arquivos; EU rodo os comandos que escrevem no banco
  (migrate/commit/etc.). Nunca por conta própria.
- **Tudo em localhost agora** (banco `whatthechip`); o deploy em produção é à noite, feito por mim. O
  banco de prod é a fonte da verdade (6.500+ known_parts, só cresce — nunca reconstruir do git).
- **O preço é tão exato quanto as specs** — a acurácia da classificação impacta o preço. Leia
  `PLANO_QUALIDADE_DADOS.md` na raiz (dívida de dados aberta). Nota: pela regra 2, RAM 3 vs 4GB não
  muda preço, mas o **subtype** tem que estar certo (LPDDR3/4X/5 mudam o preço).
- **Fonte-única + config no admin**, suíte verde: `python manage.py test chips estoque
  --settings=core.settings_test`. Toda mudança de modelo → migration; reversível.

---

## DECISÕES DE DESIGN pro BRAINSTORM (não decida sozinho)

Tabela do comprador vira modelo no banco (import do xlsx + editável nas duas telas) — como versionar
cotações por data (`Quote date`)? Como derivar a "faixa de armazenamento" do `emcp_nand` (ex.: "eMMC
5.1 64GB" → faixa 64GB)? Onde o preço aparece (card de busca / gateway do estoque / export do lote)?
Margem/rentabilidade a partir do preço do comprador integra com o `assess_profitability` ou é camada
separada? Autenticação/permissão do dashboard do comprador (multi-comprador no futuro)?

---

## COMO VAMOS TRABALHAR — BRAINSTORM PRIMEIRO

Esta sessão começa **só com brainstorm, sem implementar nada.** Depois que você **ler e entender este
prompt + a planilha anexa**, eu mando **todas as minhas considerações e features adicionais**. A gente
desenha junto; só DEPOIS implementamos.

**O que fazer AGORA:**
1. Leia este prompt e a `wuquan_prices_updated_EN.xlsx` (estrutura real + aba `Instructions`).
2. Olhe `CLAUDE.md`, `PLANO_QUALIDADE_DADOS.md`, `chips/chip_types.py` e o `assess_profitability`/
   `ProfitabilityConfig` pros padrões — e comece a **verificar a solidez da convenção dos PNs**
   (Feature 5), me dizendo se vê buraco que atrapalhe precificar em escala.
3. **Confirme que entendeu** (resume + levante dúvidas estruturais) e **ESPERE** — não proponha
   arquitetura final nem implemente. Eu mando minhas considerações na sequência e a gente brainstorma.
