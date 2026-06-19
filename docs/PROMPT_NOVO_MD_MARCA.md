# PROMPT — Montar base de conhecimento de nova marca para WhatTheChip

> Copie este prompt inteiro para um novo chat (modelo avançado).
> Substitua `[MARCA]`, `[PREFIXOS]` e `[CONTEXTO_MARCA]` pelos dados reais.
> Não use este prompt para editar código — só para pesquisa e geração do .md.

---

## INÍCIO DO PROMPT

Você vai me ajudar a criar o arquivo `[MARCA].md` — a base de conhecimento canônica
da marca **[MARCA]** para o projeto **WhatTheChip (WTC)**.

WTC é um sistema Django de classificação de chips IC para o mercado de reciclagem
eletrônica (eMiner, Paraguai). O operador lê o Part Number gravado no chip e o
sistema retorna tipo, specs e destino comercial (rentável vs. sucata).

Antes de começar qualquer pesquisa, leia os arquivos abaixo na íntegra:

1. `/path/to/chipdocs/CLAUDE.md` — regras de ouro do projeto inteiro (leia TUDO)
2. `/path/to/chipdocs/SAMSUNG.md` — modelo de referência de como o .md deve ser estruturado
3. `/path/to/chipdocs/MICRON.md` — segundo modelo de referência
4. `/path/to/chipdocs/chips/management/commands/populate_[marca].py` — gabarito atual (se existir)
5. `/path/to/chipdocs/chips/management/commands/fix_known_parts.py` — seção da marca (se existir)

Só depois de ler esses arquivos, passe para a pesquisa.

---

## CONTEXTO DA MARCA

- **Marca:** [MARCA] (ex.: SK Hynix / Kingston / Rayson / Toshiba / Sandisk / Kioxia)
- **Prefixos principais:** [PREFIXOS] (ex.: H9, H5AN, H5TQ, HMA, KMKXX...)
- **Contexto no mercado de reciclagem:** [CONTEXTO_MARCA]
  (ex.: "SK Hynix é o segundo maior fabricante de DRAM. Na esteira aparecem principalmente
  LPDDR4/4X em smartphones Android e DDR4 em notebooks.")

---

## CONVENÇÃO CANÔNICA DE CAMPOS — NÃO DESVIE

Esta é a convenção estabelecida no projeto. **Toda entrada que você criar DEVE seguir.**

### chip_type / subtype / interface por tipo de chip

| Tipo | `chip_type` | `subtype` | `interface` |
|------|------------|-----------|-------------|
| DDR1 / DDR2 / DDR3 / DDR4 / DDR5 | `"RAM"` | SOMENTE a geração: `"DDR3"`, `"DDR4"` | bus width: `"x8"`, `"x16"`, `"x4"` |
| GDDR3 / GDDR5 / GDDR6 | `"RAM"` | `"GDDR5"`, `"GDDR6"` | bus width: `"x8"`, `"x16"` |
| LPDDR1/2/3/4/4X/5/5X standalone | `"LPDDR4X"` (tipo no chip_type) | mesmo que chip_type: `"LPDDR4X"` | `""` (VAZIO — sempre) |
| eMMC | `"eMMC"` | `""` | `"eMMC"` ou versão |
| UFS | `"UFS"` | `""` | `"UFS 3.1"` ou versão |
| eMCP | `"eMCP"` | geração RAM: `"LPDDR4"` | `""` (VAZIO — sempre) |
| uMCP | `"uMCP"` | geração RAM: `"LPDDR5"` | `""` (VAZIO — sempre) |

### Regra absoluta do `subtype` — o que NUNCA colocar

`subtype` = **1 a 3 palavras, apenas a geração ou célula.**

❌ `"DDR4 PC DRAM 8Gb x8"` → label do gateway fica `"DDR4 PC DRAM 8Gb x8+8G"` (quebrado)
❌ `"LPDDR4X Mobile"` → label fica `"LPDDR4X Mobile+4G"` (errado)
❌ `"LPDDR3 Multi-Channel"` → label fica truncado na esteira
❌ `"SLC NAND industrial paralela"` → verboso demais

✅ `"DDR4"` / `"LPDDR4X"` / `"DDR3L"` / `"SLC NAND"` / `"GDDR6"`

### Regra absoluta do `interface` para LPDDR/eMCP/uMCP

**NUNCA** coloque a geração de RAM no campo `interface` para chips LPDDR, eMCP ou uMCP.
`interface="LPDDR4"` é sempre **errado**. Use `interface=""` (string vazia).
O `interface` para LPDDR não tem significado operacional no gateway de estoque.

### Por que isso importa — gateway de estoque

O gateway em `estoque/views.py` monta o label da caixa física assim:

```
DDR/GDDR  → label = f"{subtype}+{density_gbit}G"    ex: "DDR3+8G"
LPDDR     → label = f"{subtype}+{capacity_gb}G"     ex: "LPDDR4X+4G"
eMCP/uMCP → label = f"{tipo}{emcp_nand}+{emcp_ram}" ex: "EMCP64+4"
```

Qualquer texto extra no `subtype` vai direto para o label e quebra o display na esteira.

---

## REGRAS DE OURO — NÃO QUEBRE NENHUMA

1. **Escopo: só arquivos desta marca.** Não edite `populate_samsung.py`,
   `populate_hynix.py`, `populate_micron_mcp.py` nem entradas de outras marcas em
   `fix_known_parts.py`. A convenção foi corrigida neles — não reintroduza bugs.

2. **Zero invenção de dados.** Cada campo (capacidade, geração, bus width) precisa de
   fonte Tier 1 verificada. Sem fonte → sem dado.

3. **Hierarquia de fontes (imutável):**
   Datasheet oficial > Site do fabricante (ex.: product.skhynix.com) >
   Octopart com fonte fabricante > Distribuidor B2B rastreável > IA/estimativa.
   Dados de IA e de distribuidores asiáticos (Jotrin, WinSource, Shenzhen) estão
   frequentemente errados — confundem Gb/GB, invertem primary/secondary, alucinam capacidades.

4. **Nunca inverta `val_primary`/`val_secondary` nos DecodeMaps.**
   Em mapas de capacidade: `val_primary` = valor legível (ex.: `"4GB"`).
   Em eMCP: `val_primary` = NAND, `val_secondary` = RAM.
   Em mapas de densidade DRAM: `val_primary` = densidade em Gb, `val_secondary` = MB/die.
   Siga EXATAMENTE o padrão das linhas já existentes no mapa.

5. **Nunca escreva "por die" no `val_secondary`.** O engine já acrescenta " por die"
   automaticamente — se vier no mapa, duplica: "por die por die".

6. **`decode_density_type` e `decode_cap_map` são mutuamente exclusivos.**
   Nunca configure os dois na mesma família. Um produz `dram_density`, o outro produz
   `capacity`. Se ambos estiverem ativos, o engine gera dados conflitantes.

7. **Famílias com dígito numérico na 3ª posição do prefixo:** `decode_gen_pos=None`.
   Se o pn[2] for um dígito (ex.: KM1, KM5, KM8 da Samsung), não é código de geração RAM.
   O engine usa fallback ao `subtype` fixo do ChipFamily.

8. **Após `populate_[marca] --overwrite`, o servidor Django DEVE ser reiniciado.**
   O engine usa `lru_cache` — o processo do comando limpa o cache local, mas o servidor
   web continua servindo a gramática antiga até reiniciar.

9. **`status="raw"` é invisível para o engine.** Só registros com `status="enriched"`
   são usados na classificação. Se criar um KnownPart sem setar `status`, ele não funciona.

10. **`confidence="confirmed"` ou `"manual"` vencem a gramática.**
    Confianças menores (`distributor`, `ai_*`, `estimated`) perdem para a gramática se
    ela estiver completa. Para que o banco tenha precedência, use `confirmed` ou `manual`.

---

## ESTRUTURA DO ARQUIVO A PRODUZIR

Crie `[MARCA].md` com as seguintes seções, nesta ordem:

### §1 Visão Geral
- Tabela resumo: categorias × famílias mapeadas × decode completo × gaps
- Arquivos que definem as famílias (`populate_[marca].py`, `fix_known_parts.py`)
- Frequência na bancada de reciclagem (o que aparece mais)

### §2 Convenção Canônica de Campos
- Tabela: chip_type / subtype / interface para cada tipo de chip desta marca
- Campos de capacidade específicos por tipo
- Regras absolutas do subtype e interface (adaptar da convenção geral acima)

### §3 Anatomia do PN por Família
- Para cada família/prefixo: diagrama posicional do PN
- Qual posição decodifica o quê (capacidade, geração, bus width, revisão)
- Sufixos relevantes e o que significam

### §4 DecodeMaps — Inventário Completo
- Para cada mapa: nome, posição, comprimento, tabela completa de chaves
- Fonte de cada entrada (ex.: "Octopart ✓", "Datasheet ✓", "⚠️ sem PN físico")
- Status: ✅ completo / ⚠️ parcial / ❌ gap importante

### §5 Famílias — Inventário Completo
- Tabela por categoria: prefixo / chip_type / subtype / decode / prioridade / status
- Notas sobre bifurcações de prefixo, fallbacks, prioridades
- Destino comercial (rentável? qual bancada?)

### §6 fix_known_parts — Template e Regras
- Template Python correto para cada tipo de chip desta marca
- Regras de `capacity` (MB vs GB vs Gbit)
- Regra dos dois PNs (base + variante com sufixo)

### §7 assess_profitability — Limiares
- Parâmetros do ProfitabilityConfig que afetam esta marca
- Destino comercial por categoria

### §8 Armadilhas e Decisões Arquiteturais
- O que já quebrou nesta marca especificamente
- Decisões de design não óbvias (ex.: por que `decode_gen_pos=None` em certas famílias)
- Pegadinhas de nomenclatura (ex.: prefixos ambíguos, famílias com mesmo início)

### §9 Gaps e Roadmap
- O que está ausente e por quê
- Prioridade de Sprint: A (impacto imediato) → B (requer pesquisa) → C (long-tail)
- O que NÃO adicionar sem evidência Tier 1

### §10 Histórico de Correções
- Tabela: data / PN ou família / ação / fonte / motivo
- Chips confirmados individualmente com fonte

---

## WORKFLOW RECOMENDADO

**Fase 1 — Leitura (não pule esta fase)**
1. Leia CLAUDE.md completo (regras de ouro do projeto)
2. Leia SAMSUNG.md e MICRON.md como modelos
3. Leia `populate_[marca].py` e a seção da marca em `fix_known_parts.py`
4. Liste o que já existe vs. o que precisa ser pesquisado

**Fase 2 — Mapeamento das famílias**
5. Identifique todos os prefixos de PN desta marca que aparecem na reciclagem
6. Para cada prefixo: qual `chip_type` correto? qual decode posicional? qual mapa?
7. Verifique se os DecodeMaps existentes estão corretos e completos

**Fase 3 — Pesquisa Tier 1**
8. Para cada família/mapa, confirme as chaves por Octopart ou datasheet oficial
9. NÃO adicione entradas "prováveis" — só confirmadas
10. Documente a fonte de cada dado

**Fase 4 — Geração do arquivo**
11. Escreva `[MARCA].md` seguindo a estrutura acima
12. Use SAMSUNG.md como template visual (tabelas, nomenclatura, tom)
13. Não duplique conteúdo genérico do CLAUDE.md — referencie-o

**Fase 5 — Revisão**
14. Verifique: todo `interface="LPDDR*"` → `""` correto?
15. Verifique: todo `chip_type="DDR*"` de chip discreto → `"RAM"` correto?
16. Verifique: algum `subtype` tem mais de 3 palavras ou qualificadores? Corrija.
17. Verifique: os `val_primary`/`val_secondary` estão na ordem certa?
18. O arquivo está autocontido? Um agente novo consegue entender sem ler os outros?

---

## CHECKLIST ANTES DE FINALIZAR O ARQUIVO

- [ ] Toda família tem `chip_type` e `subtype` canônicos documentados?
- [ ] Interface de LPDDR/eMCP/uMCP está como `""` em todos os lugares?
- [ ] `val_primary` e `val_secondary` em cada DecodeMap seguem o padrão correto?
- [ ] Nenhum `subtype` tem qualificadores verbosos (Mobile, Multi-Channel, PC DRAM, x8...)?
- [ ] Cada dado tem fonte Tier 1 identificada?
- [ ] As armadilhas específicas desta marca estão na §8?
- [ ] O template de `fix_known_parts` usa `chip_type="RAM"` para DDR/GDDR?
- [ ] Os gaps estão listados como gaps (não como dados incompletos)?
- [ ] Mencionou que não deve tocar em arquivos de outras marcas?
- [ ] O arquivo faz sentido lido de forma independente (sem o CLAUDE.md aberto)?

---

## O QUE NÃO FAZER (erros que já cometemos)

❌ Não crie entradas de PN sem fonte — mesmo que "provavelmente exista"
❌ Não confie em dado de IA sem verificar no Octopart ou datasheet
❌ Não ponha geração RAM no campo `interface` (ex.: `interface="LPDDR4"` → errado)
❌ Não ponha informação técnica extra no `subtype` (tensão, bus width, temperatura)
❌ Não inverta `val_primary`/`val_secondary` nos DecodeMaps
❌ Não escreva "por die" no `val_secondary` (engine já acrescenta)
❌ Não crie `decode_density_type` e `decode_cap_map` na mesma família
❌ Não edite arquivos de outras marcas para "corrigir a convenção globalmente"
❌ Não use `chip_type="DDR3"` para chip DDR discreto — use `"RAM"` com `subtype="DDR3"`
❌ Não crie NAND_CAP, GDDR_CAP ou mapas novos sem confirmar as chaves por Octopart
❌ Não confunda Gb e GB (8 Gb = 1 GB — sempre verificar a matemática)
❌ Não adicione entradas eMCP com `emcp_ram="1GB LPDDR4"` — o tipo vem ANTES: `"LPDDR4 1GB"`

## FIM DO PROMPT
