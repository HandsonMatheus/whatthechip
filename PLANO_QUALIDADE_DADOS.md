# PLANO — Qualidade de Dados: known_parts *identity-only* + gramática restante

> ⚠️ **Doc de TRABALHO temporário.** Criado 2026-07-06 a pedido do dono para uma **sessão
> dedicada** de remediação de dados. É o plano de um projeto específico — **não** um handoff
> datado de rotina. Quando os dois problemas forem resolvidos, **remova este arquivo** (o que
> for durável — regra nova, decisão de arquitetura — vai pro `CLAUDE.md`, não fica solto).
> (CLAUDE.md §10 desencoraja docs soltos na raiz; este é a exceção explicitamente pedida.)

---

## 0. CONTEXTO DE SEGURANÇA — LEIA ANTES DE TOCAR EM QUALQUER COISA

Estas regras são o que impede corromper 6.500+ known_parts de produção. Nenhuma é opcional.

1. **Regra de ouro #1: o agente EDITA ARQUIVOS; o DONO roda os comandos que escrevem no banco.**
   Nunca `load_brands --commit`, `submit_known_parts --commit`, `correct_known_parts --commit`,
   `migrate` etc. por conta própria. Você propõe; o dono executa e confirma.
2. **Hoje está TUDO em localhost** (banco `whatthechip`, `localhost:5432`). **Nada foi deployado
   em produção.** O dono deploya só à noite. Não assuma prod.
3. **O banco de PRODUÇÃO é a fonte da verdade do catálogo vivo — só cresce, nunca se reconstrói
   do git** (CLAUDE.md regra §2.1b). Git = gramática (yaml) + código; o banco = os known_parts
   (6.500+). Antes de QUALQUER operação destrutiva: **backup fresco (Render Export) + revisão do
   dono**. Rode `guard_catalog` depois de todo deploy (tripwire de perda em massa).
4. **Opção 2 (modelo de dados):** known_parts vivem no **banco** (não no yaml), com revisão in-DB
   (`review_status`: draft/submitted/approved). Autoria: `submit_known_parts <arq> --commit` →
   entra `submitted` (oculto) → dono **aprova no admin** (`/admin/chips/knownpart/`). Gramática
   (famílias+mapas) vive no yaml por marca (`chips/knowledge/<marca>.yaml`), via `load_brands`.
5. **Reversibilidade sempre.** `correct_known_parts` tem `--revert <backup.json>`; mudança de
   gramática se desfaz por `git revert`. **Sempre `--dry-run` / dry-run primeiro, revisar, depois
   `--commit`.** Nunca escrita cega.
6. **Pegadinha do reload:** depois de mudar a gramática (yaml), rode `load_brands --brand <marca>
   --commit` no banco-alvo pra recarregar — senão o audit/app ainda mostram a gramática ANTIGA.
   (Foi o que fez o KMGP6001BM aparecer "errado" no meio da sessão.)
7. **Suíte verde é obrigatória** após cada mudança: `python manage.py test chips estoque
   --settings=core.settings_test` (187 testes hoje). E `characterize_baseline --diff` para
   regressão de identificação. Toda família nova → golden obrigatório em `chips/tests.py`.
8. **A rede de segurança REAL é a verificação HUMANA do dono no Octopart** (ver §4). Ela pegou
   meu erro do KM3 nesta sessão. Não trate pesquisa do agente como verdade.

---

## 1. PROBLEMA A — known_parts CONFIRMADOS sem spec própria (*identity-only*)

**O furo (levantado pelo dono, 2026-07-06):** existem known_parts `confidence=confirmed`/`manual`
com os campos de spec VAZIOS — que **dependem 100% da gramática** para exibir NAND/RAM/capacidade.
Isso **inverte a hierarquia**: `confirmed` deveria significar "tenho a spec verificada deste chip";
a gramática é o **tapa-buraco pros PNs que NÃO temos**, não uma muleta pros que temos. Um registro
"✅ Confirmado" que empresta da gramática dá **falsa confiança** ao operador — e se a gramática erra
(como no bug X6), o "confirmado" mostra errado.

**Tamanho do estrago (medido com `audit_known_parts --empty`, banco local, 2026-07-06):**

```
Confirmados/manual auditados: 6509  ·  SEM SPEC PRÓPRIA (identity-only): 876  (13,5%)
```

**Dois níveis de gravidade** (o 2º é pior):

- **~440 COBERTOS pela gramática** (têm família): Micron `MT53E/D/B`, `MT29P/TZZZ/VZZZ`, `MT30A`,
  `MT52L`; Samsung `KM8/KM5/KMD/KM2*/KM3*/KMAG/KMAS`; SK `H9TQ/H9DP/H9HP`. A gramática preenche →
  mostram **algo** (certo nas famílias já verificadas — §5; errado nas não). **Backfill resolve.**
- **~440 SEM família no grammar** (agrupados por *tipo*, não por família): `LPDDR4X`=250, `LPDDR5`=67,
  `eMCP`=43, `DDR2`=42, `eMMC`=36. Aqui o `_match_family` não casa → **a gramática NEM consegue
  preencher** → confirmado **genuinamente sem spec nenhuma** (operador vê "Confirmado" + capacidade
  em branco). **Backfill NÃO alcança; precisam de spec pesquisada de verdade.**

**Origens (contam a história):** `psg_2h2014` (import do Samsung Product Selector Guide — confirmou
a IDENTIDADE, não capturou specs); *"Confirmado manualmente pelo operador"* (SK — confirmou o PN
físico mas não digitou specs); *"Fila de revisão"* / *"Octopart Tier 1: … = 'DD…'"* (K4B — a fonte
está na `notes`, mas os campos de spec ficaram vazios).

**Plano de conserto (3 frentes):**

1. **Regra no PORTÃO (pequeno, fazer PRIMEIRO — estanca a sangria).** Em `KnownPart.clean()`
   (`chips/models.py`) e/ou no Pydantic (`chips/knowledge/schema.py`): `confirmed`/`manual` sem
   NENHUMA spec (nem `capacity`/`density_gbit`, nem `emcp_ram`/`emcp_nand`) → **rejeita ou rebaixa**
   para `estimated`. ⚠ Decidir com o dono se mantém uma **exceção documentada** pro padrão
   *identity-first* do FBGA (`enrich_micron_fbga` confirma PN↔FBGA e enche specs depois via
   `fill_capacity_from_micron_api`) — se mantiver, esses ficam num status próprio, não `confirmed`.
2. **Backfill (os ~440 com família verificada).** Construir `backfill_known_parts` (ou estender
   `correct_known_parts` com `--fill-empty`): grava a spec da GRAMÁTICA VERIFICADA **dentro** do
   registro confirmado, pra ele carregar o próprio dado. **Escopo por `--family`, só famílias
   Tier-1-verificadas (§5), dry-run/backup/revert.** ⚠ NUNCA nas famílias não-verificadas — assaria
   valor errado (a gramática ainda erra lá). Depois do backfill, o registro fica self-sufficient e o
   ciclo `audit`/`correct` mantém sincronia se a gramática melhorar.
3. **Pesquisar spec (os ~440 sem família).** O grosso e o mais lento. Precisa da pesquisa Tier-1 +
   verificação do dono no Octopart (§4). Priorizar por volume na esteira / valor comercial.

---

## 2. PROBLEMA B — gramática restante (LPDDR3 + legadas) por-família

O bug X6 (mapa `SAM_EMCP_CAP` compartilhado misturando RAM entre famílias) foi corrigido nas 12
famílias modernas (§5). **Falta remodelar as demais** com o mesmo padrão por-família (CLAUDE.md §4).

**Situação do LPDDR3 (KMF/KMQ/KMR), medida com `audit_known_parts --family KMF,KMQ,KMR`:**

```
Auditados: 59 known_part(s)  ·  DIVERGENTES: 14  ·  ok: 47
Por família: KMF=5 · KMQ=3 · KMR=6
```

**⚠ FLUXO INVERTIDO — cuidado máximo aqui:** nas famílias modernas eu consertei a gramática (Tier-1)
e o banco seguiu (`correct_known_parts` empurrou banco→gramática). **No LPDDR3 é o CONTRÁRIO:** o
**banco já é a verdade** (muitos *"chip físico confirmado na esteira (eMiner)"* — a fonte mais forte
que existe) e a **gramática (mapa compartilhado) é o elo fraco**. Então:

- **NÃO rodar `correct_known_parts` no LPDDR3** — empurraria a gramática ERRADA pro banco CERTO.
- Construir os mapas per-família **A PARTIR dos known_parts confirmados** (curando por fonte:
  chip-físico > Octopart > distribuidor). Muitos códigos + conflitos: `31`=1.5GB (KMQ310**006**) vs
  2GB (KMQ310**013**) → **pn[7]-dependente** (usa chave longa `pn[3:8]`, como KM5 L9); `X6`=4GB no
  KMR; `J2` no KMF = 4GB+512MB (o mapa base diz 128GB+6GB — grotesco); `X1`/`82`/`8X`/`E1`/`21`.
- É job grande: ~7 códigos problemáticos × 3 famílias, alguns só de distribuidor (precisam do
  Octopart do dono).

**Depois do LPDDR3, restam as legadas:** KMJ/KMK/KML/KMV (LPDDR2 — quase tudo NÃO RENTÁVEL por
geração, valor baixo), KMS (LPDDR1), KM1 (LPDDR5X — **sem dado nenhum**, precisa de PNs da esteira).

---

## 3. FERRAMENTAL (construído nesta sessão — já commitado)

- **`audit_known_parts`** (read-only, `chips/management/commands/`):
  - Padrão: compara known_parts confirmados vs decode PURO da gramática (`_result_from_family`,
    ignorando o registro), lista divergências. Escopo `--brand`/`--family`. `--out <csv>`.
  - `--empty`: lista os confirmados/manual SEM spec própria (o Problema A). Checa os campos certos
    por tipo (`emcp_ram`/`emcp_nand` pra eMCP; `capacity`/`density_gbit` pra discreto).
- **`correct_known_parts`** (par de escrita): corrige stale banco→gramática. **Dry-run padrão**,
  `--commit`, **backup JSON + `--revert`**, `--exclude PN`, `--family`, `--sync-subtype`, escrita
  pelo portão (`save()`→full_clean→bump `catalog_version`). ⚠ Só usar quando a GRAMÁTICA é a fonte
  (famílias modernas). **NÃO no LPDDR3** (fluxo invertido — §2).
- **Ciclo típico (localhost):** `load_brands --brand samsung --commit` → `audit_known_parts …` →
  `correct_known_parts … --dry-run` (revisar) → `… --commit` (backup automático) → `--revert` se
  algo estranhar.

---

## 4. LIÇÕES desta sessão (NÃO repetir os erros)

- **Distribuidor NÃO vale para capacidade.** "64+48"/"XX+YY" de Preduo/Alibaba/Puris/WinSource
  erram e **invertem Gb/GB**. Nesta sessão isso me fez shipar KM3 (KM3H/KM3P) como 6GB — o Octopart
  do dono mostrou 4GB, e revertei (`git revert`). **Capacidade só de Octopart ou datasheet lido;
  broker é PISTA a confirmar, nunca verdade.** (SK_HYNIX.md §6 já avisava — WinSource/Jotrin invertem.)
- **⚠ Páginas oficiais da Samsung NÃO renderizam** (client-side; produtos EOL redirecionam pra
  categoria genérica). Um resumo de busca dizendo "página Samsung = X" costuma ser a IA repetindo o
  distribuidor. **Não chamar de "oficial" sem LER a página.**
- **Mesma chave ≠ mesma RAM entre famílias** (a essência do bug X6). Provado: `V8001` = 6GB (KM2) /
  4GB (KM5) / 8GB (KM8); `X6` = 3GB (KMD/KMG) / 2GB (KM4); `P6` = 4GB (KMD LPDDR4X, 32Gb) / 3GB (KMG
  LPDDR3, 24Gb) / 6GB (KM3, 48Gb). **Nunca reusar valor de um código entre famílias.**
- **A verificação humana do dono é a rede de segurança.** O agente pesquisa e apresenta candidatos;
  o **dono confere no Octopart** e arbitra. Dois chats de marca em paralelo é seguro no técnico
  (dados disjuntos, escrita serializada pelo dono), mas **divide a atenção do dono** — a régua de
  desconfiança não pode afrouxar.

---

## 5. STATUS — o que já foi feito (sessão 2026-07-06, tudo LOCAL, nada deployado)

**12 famílias eMCP/uMCP Samsung remodeladas por-família** (mapa próprio, exceto KM3 que ficou no
compartilhado a 4GB, confirmado): `KMD, KMG, KM4, KM5, KM8, KM2, KM2L, KM2P, KMAG, KMAS` (+ `KM3H/
KM3P` = 4GB confirmado Octopart). Padrão em CLAUDE.md §4 (letra=split NAND+RAM; dígito=combinado;
chave longa `pn[3:8]` no pn[7]-dependente).

**Correção de banco (local) já aplicada** nas modernas: 4 stale corrigidos (`KM4X6001KM` type,
`KM8V8001JM` 4→8GB, `KMDX6001BM` e `KMGX6001BM` 2→3GB) via `correct_known_parts --commit` (backup
reversível guardado). Auditoria: 42/46 já batiam.

**Sub-itens ABERTOS** (anotar, resolver quando puder):
- **KMDD (código D) = LPDDR4, não LPDDR4X?** Octopart mostrou `KMDD60018M` como "LPDDR4" e
  `KMDX60018M` como "LPDDR4X". A capacidade (3GB) está fechada; só o **tipo** ficou em aberto —
  confirmar se `pn[3]='D'`→LPDDR4 e `'X'`→LPDDR4X, e separar no mapa se for.
- **KMD `P6`/`H6` = 4GB** confirmado nesta sessão (KMDP6001DA = 64GB+32Gb=4GB; genuinamente ≠ KMG
  P6=3GB e KM3 P6=6GB). OK.
- **KM1** (LPDDR5X) sem dado — precisa de PNs da esteira.

**Commits desta sessão** (locais, não pushados): bug X6 por família (KMD→KMAS), correção de KMG P6
(pego pelo audit), o toolchain `audit_known_parts`/`correct_known_parts` (+ `--empty`), e o revert
do KM3. `git log --oneline` mostra tudo.

---

## 6. ORDEM DE ATAQUE recomendada (próxima sessão)

1. **Regra no portão** (Problema A, frente 1) — pequena, estanca a criação de novos confirmados-vazios.
   Decidir a exceção FBGA com o dono.
2. **Backfill** (Problema A, frente 2) — construir o comando + rodar nas ~440 famílias verificadas.
   Baixo risco (dry-run/revert), alto valor (tira as modernas da muleta da gramática).
3. **LPDDR3 por-família** (Problema B) — construir da fonte-banco, com Octopart do dono nos códigos
   de distribuidor. Fluxo INVERTIDO (não rodar `correct`).
4. **Pesquisar specs dos ~440 sem-família** (Problema A, frente 3) — o grosso, contínuo, por volume.
5. Legadas (KMJ/KMK/KML/KMV/KMS) e KM1 — menor prioridade.

> Ao terminar: dobrar o durável (regra do portão, decisão do backfill) no `CLAUDE.md` e **apagar
> este arquivo**.
