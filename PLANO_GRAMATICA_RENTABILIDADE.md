# PLANO — Trilha de GRAMÁTICA + correção de RENTABILIDADE (rumo ao PREÇO)

> ⚠️ **ARQUIVO TEMPORÁRIO / DE TRABALHO.** Apagar quando implementado; conteúdo durável vai pro CLAUDE.md.
> Continua o trabalho da Opção 2. Sessão 2 (adiada): a trilha de edição de GRAMÁTICA + o elo comercial.

## Objetivo (atacar para quê)

Fechar o **caminho do herói de um PN** até a **decisão comercial correta** — não só "decodificou o tipo",
mas "o operador recebe rentável? + (em breve) preço", com as falhas **previstas e travadas**. A saída
canônica da classificação — **(chip_type, subtype, capacidade)** — é a **chave de junção do preço**, então
convenção limpa (Opção 2) deixou de ser organização e virou o índice comercial.

## Grounding (medido no catálogo real de 6.549, não suposição)

- **767 PNs (~12%) dão INDETERMINADO hoje** → operador sem decisão. Dividem em DUAS causas:
  - **(i) tipo sem regra** (~56): GDDR3/5/6 (K4G/K4J/K4Z) — `assess_profitability` não conhece GDDR.
  - **(ii) capacidade não decodificou** (~700): Micron `-DC`, eMCP/uMCP sem ram/nand → a regra não tem dado.
- **24 chip_types** no catálogo = a dimensão da futura chave de preço (tipo × geração × faixa de capacidade).

## Bugs concretos confirmados (evidência no código)

1. **INDETERMINADO renderiza como "Rentável: sim" (verde).** `estoque/views.py:467-469`: no passo 3 do
   gateway, INDETERMINADO recebe `status='pass'` (o mesmo do RENTÁVEL) → o frontend mostra "sim" confiante
   num chip **não avaliado**. Sistêmico: vale pra todo tipo futuro que caia em INDETERMINADO.
2. **GDDR ausente da rentabilidade.** Não está em `ProfitabilityConfig` nem em `assess_profitability`
   (docstring: "GDDR3+ sem threshold → INDETERMINADO"). Dono decidiu: **GDDR3+ é RENTÁVEL**.
3. **Mapas globais desprotegidos.** `load_brands._upsert_maps:135`: qualquer marca que nomeie um mapa
   `DRAM_PC`/`DRAM_MOBILE` grava com `brand=None` e sobrescreve o global de TODAS as marcas. Famílias têm
   guard (✓); mapas não.
4. **Portão valida convenção, não estrutura do decode.** Não pega `cap_pos` sem `cap_map`, posição ≥
   `pn_length`, `gen_pos` sem `gen_map` → falha silenciosa/placeholder no runtime.
5. **`_match_family` depende de `priority`, não do prefixo mais longo** (`engine.py:307` ordena
   `priority, -prefix_len`). Família nova com `priority` baixa + prefixo curto **sequestra** PNs de outra.
   `characterize --diff` só pega isso pros PNs que JÁ existem — família nova não tem baseline.

## As peças (mecanismos, não "mais regras na doc")

**A. Teste-golden por família (a espinha).** Toda família nova/editada entra com N **PNs âncora + saída
esperada**: `chip_type`, `subtype`, `capacidade` E **rentabilidade** (e o campo de **preço** encaixa quando
existir). Isso:
- prova o **decode novo** (o `characterize` não consegue — sem baseline pro PN novo);
- é o **handshake**: se o tipo novo cair em INDETERMINADO, o golden **falha** → força declarar a regra;
- pega **hijack de priority** (o âncora de outra família muda → o golden dela quebra).
- Formato provável: um yaml/py `golden` por marca — `[{pn, chip_type, subtype, capacity, profitable}]`,
  rodado na suíte + `characterize`. (Ver Samsung/Micron pra fechar o formato — TODO.)

**B. Handshake de rentabilidade.** Um `chip_type` canônico que caia em INDETERMINADO **não passa** —
tem que estar declarado em `chip_types.py::profit_family` (dead/emcp/emmc/ufs/lpddr/ddr/gddr) ou
explicitamente marcado. Enforcement via o golden (B ⊂ A) + um check dedicado.

**C. Fix da apresentação INDETERMINADO ≠ RENTÁVEL.** Passo 3 do gateway ganha um **estado distinto**
(`status='warn'`/`'indeterminado'`, âmbar "indeterminado") — NÃO o verde "sim". Regra de negócio
(INDETERMINADO → entra no estoque) **não muda**; muda o que o operador VÊ (honesto). Template do estoque
renderiza o 3º estado. *(Segurança sistêmica: mesmo com o handshake, se algo escapar, não mente "sim".)*

**D. Guard de mapa global.** `load_brands` recusa `DRAM_PC`/`DRAM_MOBILE` em yaml de marca não-dona
(só Samsung escreve; resto referencia). Espelha o guard cross-brand de famílias.

**E. Validadores estruturais no portão** (`FamilySpec`): `cap_pos` exige `cap_map`; `gen_pos` exige
`gen_map`; posições de decode `< pn_length` (quando setado); `cap_len`/`gen_len` coerentes.

**F. `reasoning` obrigatório por família** (o campo já existe no modelo) = a **fonte Tier-1 da regra de
decode** (a proveniência que a gramática, ao contrário do known_part, não exigia).

**G. Regra GDDR** (business, decisão do dono): GDDR3+ = RENTÁVEL; GDDR2- = NÃO RENTÁVEL. Adicionar
`gddr_min_gen` (já existe? confirmar) + faixa ao `ProfitabilityConfig` + branch em `assess_profitability`.

## Pricing-readiness (o preço vem "em breve" — não construir agora, mas não retrabalhar)

- **Rentabilidade = fonte única** (regra #11); **preço = downstream** que consome a saída canônica — nunca
  reimplementa lógica de tipo.
- **Tabela de preço = data-driven no banco** (como `ProfitabilityConfig`, editável no admin), chave
  (tipo × geração × faixa de capacidade).
- **Guard de combo-sem-preço**: classifica mas sem linha de preço → sinaliza (nunca €0 silencioso). Mesmo
  padrão do handshake de rentabilidade.
- O **teste-golden já nasce com o campo de preço** (mesmo que vazio hoje) pra não retrofitar.

## Backlog dos 767 INDETERMINADO (ganho direto pro operador)

- **GDDR (~56):** resolvido pela peça **G** (regra). Vira RENTÁVEL na hora.
- **Micron capacidades não-decodificadas (~700): FASE 2** — o **chat da Micron** decodifica (é decode de
  gramática) e passa pro dono preencher. Não é adivinhação minha.
- **`chip_type=''` (1, TY890…):** decode nulo — investigar à parte.

## Fases (cada uma testável, characterize --diff controlado)
- **F1 — Fix de segurança (rápido, alto valor):** peça **C** (INDETERMINADO ≠ verde) + peça **G** (regra GDDR).
  Testes: K4W…/K4G…/K4J…/K4Z… → RENTÁVEL; um tipo fake desconhecido → 3º passo âmbar, não "sim".
- **F2 — Travas de gramática:** peças **D** (guard mapa global), **E** (validadores estruturais), **F** (reasoning).
- **F3 — Teste-golden + handshake:** peças **A** + **B** (a espinha) — formato do golden lido de Samsung/Micron.
- **F4 — Docs (CLAUDE.md §5 trilha de gramática) + memória + regressão final (subagente).**
- **(Fora daqui) Preço:** projeto próprio, sobre a base pricing-ready.

## Decisões do dono (o sistema força a pergunta; o valor é seu)
- GDDR: threshold exato (GDDR3+ tudo rentável? ou tem faixa de densidade?).
- (Futuro) faixas de preço por (tipo × geração × capacidade).

## Checklist de execução
- [ ] F1 fix segurança (C+G) + testes · [ ] F2 travas (D+E+F) · [ ] F3 golden+handshake (A+B) ·
  [ ] F4 docs+regressão · [ ] apagar este arquivo.
