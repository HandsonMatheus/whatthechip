> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da Nanya (3 famílias DDR magras) vive em
> **`chips/knowledge/nanya.yaml`** (via `load_brands`). Os **known_parts** (PNs confirmados = autoridade)
> **NÃO ficam no yaml** — vivem no **banco**, submetidos por `submit_known_parts` e **aprovados pelo dono**
> no admin (four-eyes). **Processo obrigatório completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados (decode key→valor, known_parts): esses vivem
> no **yaml** (gramática) e no **banco** (known_parts). Aqui ficam: **convenções, anatomia do PN,
> armadilhas, rentabilidade (princípio), fontes, o *porquê*** e ponteiros.

---

# NANYA.md — Bíblia Técnica e de Negócio

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/nanya.yaml`). Regras gerais do WTC: `CLAUDE.md`.

Nanya Technology — Taiwan, fundada em 1995 (spin-off da Formosa Plastics). Fabricante de **DRAM discreta**
(SDRAM/DDR/LPDDR) — **sem** linhas eMMC/UFS/eMCP/uMCP/NAND (Nanya é **DRAM-only**). Aparece o tempo todo em
roteadores, modems, TVs, set-top boxes e notebooks — alto volume na bancada, mas 2º escalão de liquidez B2B
frente a Samsung/SK Hynix/Micron. O yaml hoje tem **3 famílias** (todas DDR de PC/notebook) — a lista viva
está no yaml.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/nanya.yaml            ← GRAMÁTICA (3 famílias DDR). SÓ isso (Opção 2).
banco (submit_known_parts→aprovação)  ← known_parts confirmados = autoridade (não no yaml)
AUTORIA.md / CLAUDE.md §5             ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** → edita o yaml → `load_brands --brand nanya`
(dry-run = portão) → o **dono** roda `--commit`. **known_parts** (autoridade) → `submit_known_parts`
(dry-run) → o **dono** roda `--commit` + **aprova no admin**. ⚠ **Família nova → PN-âncora no golden é
OBRIGATÓRIO** (`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:** `chips/engine.py`,
`estoque/views.py`, yamls/known_parts de outras marcas, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono =
Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca `load_brands --commit`/`migrate` sem confirmação.
2. **`load_brands --brand nanya` (dry-run) é o portão** — valida a convenção, nada gravado. Depois `--commit`
   (recarrega o cache sozinho, sem restart).
3. **A GERAÇÃO vai no `chip_type`** (`DDR3L`, `DDR4`…), espelhada no `subtype`. ❌ NUNCA `chip_type="RAM"`/
   `"DDR"` genérico. Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ a geração** (1–3 palavras). ❌ densidade, bus width, tensão, `"Low Voltage"`, `"SDRAM"`.
5. **Nanya é DRAM-only.** Não force `emcp_ram`/`emcp_nand`/`capacity` (GB) de eMMC/UFS — não se aplicam. A
   família é sempre DDR-PC (`density_gbit`, Gb/die) ou, quando confirmada, LPDDR mobile (`capacity`, GB).
6. **As 3 famílias atuais (`NT5AD`/`NT5CC`/`NT5PA`) NÃO decodificam capacidade** — `decode_cap_pos: null` e
   `decode_density_type: ''` nas três. Sem `known_part`, o PN sai só com o tipo e cai em **INDETERMINADO**
   (as 3 famílias confirmam isso no golden — todo PN-âncora resolve INDETERMINADO). **Popular `known_parts`
   não é incremental aqui — é a ÚNICA forma de qualquer PN Nanya ganhar capacidade/rentabilidade hoje.**
7. **`NT5CB` (DDR3 1.5V) não tem `ChipFamily` própria** — só existe via `known_parts` individuais. Um PN
   `NT5CB…` sem known_part confirmado é **invisível** ao `classify()` (nem reconhecimento de tipo). Ver §3.
8. **`NT5CC` = DDR3L (1.35V) ≠ `NT5CB` = DDR3 (1.5V)** — a 5ª letra do prefixo (`C` vs `B`) é o que
   distingue; corrigido jul/2026 (antes `NT5CC` caía em DDR3 genérico).
9. **Não confie em distribuidor/IA sem verificar** (confundem Gb/GB, alucinam capacidade). Mesmo num
   `confidence=confirmed`, o que está atestado é a **identidade** — `density_gbit`/`capacity` são
   derivados e podem estar errados; atestar sempre em Tier-1.

### 0.3 Hierarquia de fontes (imutável)

```
1. nanya.com.tw (datasheet oficial) / Octopart-Nexar (categorização própria) — Tier 1
2. DigiKey, LCSC, Alldatasheet — Tier 2, rastreável à Nanya
3. Mouser, Chip1Stop — Tier 2/3, apoio
4. Jotrin, distribuidor B2B genérico — Tier 3, só apoio; nunca decisivo pra capacidade
5. Wayback Machine — pra páginas/specs de PN descontinuado
6. IA externa — ÚLTIMO RECURSO; verificar SEMPRE
```
Nunca fonte primária: fóruns, catálogos genéricos sem rastreio, eBay, IA sem verificação.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **Fonte única: `chips/chip_types.py`.** Contexto geral: `CLAUDE.md §6`. DRAM discreta: geração no
> `chip_type`, espelhada no `subtype`. Unidade: die em `Gb`, pacote em `GB`.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR3L / DDR4 (PC — famílias na gramática hoje) | a geração (`DDR3L`, `DDR4`) | espelha | bus width (`x8`/`x16`), só via known_part | `density_gbit` (Gb/die) — **só via known_part**, a gramática não decodifica |
| SDRAM / DDR1 / DDR2 / DDR5 (citadas no site institucional, SEM família na gramática) | a geração, quando confirmado Tier-1 | espelha | idem | idem — pesquisar antes de criar `ChipFamily` (§5) |
| LPDDR3–LPDDR5 (citadas no site institucional, SEM família na gramática) | a geração (`LPDDR3`…`LPDDR5`) | espelha | `""` | `capacity` (pacote, GB) — idem, ver §5 |

**Regras absolutas:** `subtype` = só a geração (nunca `"4Gb"`, `"x16"`, `"1.35V"`, `"Low Voltage"`, `"SDRAM"`).
`density_gbit` = Gb por die (campo `TextField` do `KnownPart`, ex. `"4Gb"`). `capacity` = pacote em bytes,
nunca Gbit. `tip`/`notes` = tensão, temperatura, organização, fonte.

**Label da caixa:** DDR `{subtype}+{density_gbit}G` (ex.: `DDR3L+4G`) · LPDDR `{chip_type}+{cap GB}G`
(quando a família existir).

---

## 2. Anatomia do PN — como LER um chip Nanya

> A estrutura observada — os valores/mapas completos (quando existirem) vivem no yaml. Aqui fica o padrão
> e as pegadinhas.

**Formato geral:** `NT5[família de 2 letras][profundidade]M[largura]-[sufixo de velocidade/temp/revisão]`
— ex.: `NT5CC256M16EP-DI`. O prefixo de 5 caracteres já entrega a geração inteira (diferente de
Samsung/SK Hynix, aqui não é 1 posição com tabela de código — é o prefixo inteiro que muda):
`NT5CC`→DDR3L (1.35V) · `NT5CB`→DDR3 (1.5V, só via known_part, regra de ouro #7) · `NT5AD`→DDR4 ·
`NT5PA`→DDR3L (variante notebook). A página de documentação institucional da marca (CMS, não Tier-1)
também cita `NT5SV`/`NT5S`→SDRAM, `NT5DS`→DDR1, `NT5TU`→DDR2, `NT5AN`→DDR4, `NT5W`→DDR5,
`NT6CL`/`NT6TL`→LPDDR3, `NT6AN`→LPDDR4, `NT6AH`/`NT6AP`→LPDDR4X, `NT6AC`→LPDDR5 — **nenhum desses tem
família na gramática ainda**; tratar como lead de pesquisa, não como fato confirmado (§5).

**⚠ Hipótese de decode de capacidade (NÃO implementada — confirmar antes de usar):** cruzando os
`known_parts` já confirmados (seed local) com o exemplo documentado no yaml (`NT5CC256M16EP-DI =
256M×16bit = 4Gb`), o bloco depois do prefixo parece seguir literalmente `[profundidade em M]M[largura em
bits]` — ex.: `128M16` = 128M×16 = 2Gb (256MB); `256M8` = 256M×8 = 2Gb (256MB). Ou seja, a capacidade pode
estar **escrita por extenso no PN** (fórmula profundidade×largura÷8 — o mesmo princípio já usado no decode
de outra marca via fórmula, CLAUDE.md §7), não codificada por char+tabela como Samsung/SK Hynix. **Não vira
`decode_cap_map`/mecanismo de fórmula sem confirmar em datasheet oficial** (a notação pode mudar entre
gerações DDR3→DDR4→DDR5) **e sem alinhar com o dono** — seria mudança estrutural de decode, fora do escopo
de só editar o yaml.

**Sufixo:** não codifica capacidade — é velocidade/temperatura/revisão de package (`-DI`, `-EK`, `FPDI`,
`JREKT`…). Não usar pra decodificar specs.

---

## 3. Armadilhas e Decisões Arquiteturais

- **`NT5CC` ≠ `NT5CB`** — DDR3L (1.35V) vs DDR3 (1.5V). Corrigido jul/2026 (`NT5CC` caía em DDR3 genérico
  antes). A letra que distingue é a 5ª do prefixo.
- **`NT5CB` sem `ChipFamily`** — hoje só existe no catálogo via `known_parts` individuais confirmados; um PN
  `NT5CB` novo (sem known_part) não é reconhecido nem como "tipo DDR3" — fica 100% invisível ao `classify()`.
  Avaliar com o dono se compensa criar a família (mesmo sem decode de capacidade, ganharia reconhecimento
  de tipo — igual às outras 3).
- **As 3 famílias da gramática não decodificam capacidade** — sinalizado pelo próprio `load_brands` no
  censo de 2026-07-11 (família DDR-kind sem NENHUMA fonte de densidade, junto com PieceMakers). Não é bug —
  é o estado atual, documentado; a lacuna se fecha por `known_part`, não por decode automático (por ora). A
  gramática da Nanya é a "válvula de escape" mais estreita do catálogo — o banco confirmado carrega quase
  todo o peso da classificação real.
- **Bug do "lote 40" (2026-07-11) tocou famílias como a Nanya:** `known_parts` de família DDR-kind sem
  decode de densidade própria (SK Hynix e Nanya) podiam ter `capacity` preenchido (bytes-por-die) sem
  `density_gbit` — o preço quebrava (`NO_KEY`). Hoje mitigado no engine (auto-preenchimento no save + aviso
  do `load_brands`), mas ao submeter um `known_part` novo, **preencha `density_gbit` explicitamente** (não
  confie só no `capacity`).
- **Nanya é DRAM-only** — não esperar/forçar eMMC, UFS, eMCP, uMCP ou NAND Flash pra essa marca.
- **A tabela do site institucional (página de documentação da marca, conteúdo CMS) não é fonte Tier-1** — é
  referência para o operador de bancada, não verificada família-a-família contra datasheet. Útil como lead
  de pesquisa (§5), nunca como base pra criar `ChipFamily` sem confirmação própria.

---

## 4. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no **`ProfitabilityConfig`**
(admin, você edita). ⚠ **É dado mutável** — por isso este doc **NÃO cita valores nem veredictos por
geração** (dataria no dia seguinte). Regra durável: sem `density_gbit`/`capacity` preenchido corretamente
(nunca Gbit num campo de GB) o resultado cai em **INDETERMINADO**, não em "não rentável" — para a Nanya
isso é o estado **padrão** de qualquer PN sem known_part (regra de ouro #6), não uma exceção rara.
`is_dead_by_generation` manda geração morta ao descarte mesmo sem confirmação no banco (a lista de
gerações vive no código/config, não aqui).

---

## 5. Gaps e Roadmap (o durável — o resto está no yaml)

- **Cobertura de `known_parts` hoje:** no dump disponível localmente, só `NT5CB`/`NT5CC` (DDR3/DDR3L,
  organizações `128M16`/`256M16`/`256M8`) têm PN confirmado. **`NT5AD` (DDR4) e `NT5PA` (DDR3L notebook)
  têm PN-âncora no golden de teste, mas nenhum `known_part` real no catálogo ainda** — prioridade alta
  (sem eles, todo PN dessas duas famílias é INDETERMINADO na prática). Lembrar: o banco de produção é a
  fonte viva e pode já ter avançado além deste snapshot local.
- **Famílias citadas no site institucional, ausentes da gramática** — pesquisar Tier-1 antes de criar
  `ChipFamily` + golden: `NT5SV`/`NT5S` (SDRAM), `NT5DS` (DDR1), `NT5TU` (DDR2), `NT5AN` (DDR4 — variante de
  `NT5AD`?), `NT5W` (DDR5), `NT6CL`/`NT6TL` (LPDDR3), `NT6AN` (LPDDR4), `NT6AH`/`NT6AP` (LPDDR4X), `NT6AC`
  (LPDDR5). Candidatos adicionais vistos em ferramentas de coleta locais: `NT5CA`, `NT5CD`, `NT6CM`,
  `NT6CP`, `NT8GA` (hipótese não confirmada: `NT8*` = LPDDR4X). Nenhuma família nova sem PN-âncora + fonte
  Tier-1 (AUTORIA.md §3.3).
- **`NT5CB` sem `ChipFamily`** (ver §3) — decidir com o dono se cria família type-only (sem decode de
  capacidade, só reconhecimento de tipo, igual às outras 3) para não deixar PN novo 100% invisível.
- **Hipótese de decode profundidade×largura** (§2) — vale investigar se virar mecanismo de decode
  automático, se a notação se confirmar estável entre gerações; é mudança estrutural, não decidir sozinho.
- **NÃO adicionar** família ou chave por padrão/analogia — só com PN âncora + fonte Tier-1.

---

## 6. Fontes de pesquisa

Tier 1: `nanya.com.tw` (datasheet oficial), Octopart/Nexar (categorização própria). Tier 2: DigiKey, LCSC,
Alldatasheet, Mouser, Chip1Stop. Tier 3 (só apoio): Jotrin, distribuidor B2B genérico. Wayback Machine para
specs de PN descontinuado. **Evitar para capacidade:** distribuidor sozinho, IA sem verificação — sempre
conferir `Xbit ÷ 8 = YB`.

---

## 7. Histórico (o *porquê* — durável)

- **jul/2026:** `NT5CC` corrigido de DDR3 genérico para **DDR3L** (1.35V) — a distinção de `NT5CB` (DDR3
  1.5V) é a 5ª letra do prefixo, não um sufixo.
- **2026-07-11 (bug do "lote 40"):** famílias DDR-kind sem decode de densidade própria (SK Hynix e Nanya)
  podiam gerar `known_part` com `capacity` preenchido e `density_gbit` vazio → preço quebrava (`NO_KEY`).
  Mitigado no engine (auto-preenchimento + aviso do `load_brands`); ao submeter known_part novo, preencher
  `density_gbit` explicitamente continua sendo a prática correta.
- **Opção 2 (jul/2026):** known_parts saíram do yaml — vivem no banco, com revisão in-DB
  (`submit_known_parts` → aprovação). O yaml de Nanya hoje é só gramática (3 famílias).

> O inventário de famílias vive no **`nanya.yaml`** (gramática); os **known_parts** confirmados (com a
> proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2), submetidos via `submit_known_parts`. Tudo
> cross-marca (comandos, convenção, rentabilidade, arquitetura) está no **CLAUDE.md** — o único `.md`
> mantido cross-marca, e é quem aponta pro contrato de autoria do yaml.

---

> **Regra de trabalho:** Claude edita a `nanya.yaml` e monta submissões de `known_parts`. O usuário roda
> `load_brands --brand nanya` (dry-run antes do `--commit`) e `submit_known_parts` (idem). **Ponto mais
> importante da Nanya:** a gramática não decodifica capacidade — praticamente todo o valor que este chat
> entrega vem de `known_parts` bem pesquisados e citados, não de gramática nova.
