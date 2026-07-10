# PLANO — Qualidade de Dados: known_parts *identity-only* + gramática restante

> ⚠️ **Doc de TRABALHO temporário.** Criado 2026-07-06 a pedido do dono para uma **sessão
> dedicada** de remediação de dados. É o plano de um projeto específico — **não** um handoff
> datado de rotina. Quando os dois problemas forem resolvidos, **remova este arquivo** (o que
> for durável — regra nova, decisão de arquitetura — vai pro `CLAUDE.md`, não fica solto).
> (CLAUDE.md §10 desencoraja docs soltos na raiz; este é a exceção explicitamente pedida.)
>
> **🔄 Atualizado 2026-07-09.** Remedição no banco local corrigiu a estimativa de 06/07: o buraco
> real é **816** identity-only (não ~440), **98% Micron** — e o **backfill foi RISCADO** como
> estratégia de confirmação (não confirma nada; congelaria bugs de gramática — o dono derrubou a
> ideia, com razão). O caminho é **Tier-1 por PN**. Detalhes em §1.1–1.4; ordem de ataque nova em
> §6. SK Hynix já zerou.

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

### 1.1 — Medição REAL (2026-07-09) — corrige a estimativa de 06/07

A medição de 06/07 (`audit_known_parts --empty`) separava só por *"tem família?"* → deu ~440/~440.
Era **otimista demais**: **ter família ≠ a gramática decodificar a capacidade** (muita família Micron
casa o prefixo mas não fecha a spec). Remedi com um teste mais rígido — *"a gramática produz uma
capacidade COMPLETA para este PN?"* (script em §3.1). Banco local, 2026-07-09:

```
IDENTITY-ONLY (confirmed/manual approved, sem spec própria): 877
  BACKFILL alcança (gramática decodifica COMPLETO):  61   → Samsung 30 · Micron 27 · SK Hynix 4
  FICAM (gramática NÃO decodifica → só Tier-1 resolve): 816 → Micron 799 · Samsung 17 · SK Hynix 0
```

**A virada:** o buraco real não são 440, são **816** — e **98% é Micron** (os registros do enrichment
FBGA que nasceram sem `emcp_*`/`capacity` e cuja família Micron não decodifica; ver CLAUDE.md armadilha
`enrich_micron_fbga` não salva `emcp_*`). **SK Hynix zerou** (o dono já remediou — memória
`wtc-identity-only-remediacao`). Samsung ficou com resíduo pequeno (17).

**Origens (contam a história):** `psg_2h2014` (import do Samsung Product Selector Guide — confirmou a
IDENTIDADE, não capturou specs); *"Confirmado manualmente pelo operador"* (SK — confirmou o PN físico
mas não digitou specs); enrichment FBGA Micron (confirma PN↔FBGA, deixa a capacidade pro
`fill_capacity_from_micron_api` que nem sempre rodou).

### 1.2 — Por que o BACKFILL não é a solução (retratação da frente 2 de 06/07)

O plano de 06/07 tratava o **backfill** (gramática → registro) como "conserto" dos ~440 com família.
**O dono derrubou a ideia, com razão (2026-07-09):** copiar o que a gramática calcula pra dentro do
registro e manter o carimbo `confirmed` **não confirma NADA** — é a mesma conta da gramática com outro
rótulo, **zero verificação nova**. Pior: onde a gramática erra (foi exatamente o caso do **bug X6**), o
backfill **congelaria o erro como "confirmado"** — o oposto do objetivo. ⇒ **Backfill como estratégia
de confirmação está RISCADO.**

> Única exceção legítima, e é **tática de migração, não confirmação**: congelar valores de uma família
> **verificada** dentro dos registros ANTES de aposentar/reescrever aquela gramática. Fora disso, não.

### 1.3 — O que TORNA uma spec confiável (as duas vias legítimas)

Uma spec só merece o carimbo quando vem de uma destas duas fontes:

1. **Registro Tier-1 por PN** — a spec daquele PN batida contra datasheet do fabricante / Octopart e
   gravada no known_part (`submit_known_parts` → aprovação). **É a meta do projeto.**
2. **Família de gramática verificada** — regra posicional construída + testada por *golden* a partir de
   datasheets Tier-1. É confirmação no nível da **REGRA**, não do PN.

Os **61** "backfill-able" caem na via 2: já são servidos por gramática (em boa parte) verificada — por
isso **exibem certo hoje**. Não estão "desconhecidos", estão cobertos por regra. Os **816** não têm via
1 nem via 2 → só a **via 1 (Tier-1 por PN)** resolve.

> **Ponto de fundo (dono, 2026-07-09):** o carimbo "Confirmado" num registro identity-only confirma a
> **IDENTIDADE** (o PN existe / o FBGA bate), **não a SPEC** — o próprio CLAUDE.md já diz isso dos FBGA
> Micron ("o ouro é só a identidade; capacity/subtype/density atestar sempre em Tier-1"). Opção futura
> (mudança de código, decisão do dono): deixar isso explícito na tela — distinguir "identidade
> confirmada / spec da gramática" de "spec confirmada".

### 1.4 — Plano de conserto (reordenado por VALOR REAL)

1. **Regra no PORTÃO (fazer PRIMEIRO — estanca a sangria).** Em `KnownPart.clean()`
   (`chips/models.py`) e/ou no Pydantic (`chips/knowledge/schema.py`): `confirmed`/`manual` sem NENHUMA
   spec (nem `capacity`/`density_gbit`, nem `emcp_ram`/`emcp_nand`) → **rejeita ou rebaixa** para
   `estimated`. ⚠ Decidir com o dono a **exceção documentada** pro padrão *identity-first* do FBGA — se
   mantiver, esses ficam num status próprio (ex.: `identity`), **não `confirmed`**. Isto sozinho já
   resolve a **desonestidade do rótulo**.
2. **Pesquisar spec Tier-1 dos 816 — é O TRABALHO.** Prioridade absoluta = **Micron 799**. Mas ANTES de
   pesquisar 799 à mão: quebrar por *tipo / tem-família / PN em formato raw* (script a construir, §3.1)
   pra separar o **recuperável barato** (re-rodar `fill_capacity_from_micron_api`; PN raw com
   hífen/espaço que não casou `_match_family` e normaliza) do que **exige datasheet manual**. Só o
   resíduo caro vira pesquisa PN-a-PN (Tier-1 + verificação do dono, §4). Priorizar por **rentabilidade**
   (lixo dead-by-gen / sub-mínimo → capacidade é irrelevante, pula — memória `wtc-identity-only-remediacao`).
3. **Os 61 (grammar-covered) — baixa prioridade.** Já exibem certo. Tier-1 aqui é só **procedência real
   por PN**, não conserto visível. Dos 61, subir os **27 Micron** antes dos 30 Samsung (menos confiança
   na gramática Micron); os 30 Samsung a gramática já está endurecida (§5). **Não** fazer backfill (§1.2).

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

### 3.1 — Script de categorização (o que gerou os números de §1.1)

Read-only, roda no banco-alvo. Separa identity-only em *backfill alcança* (gramática COMPLETA) vs
*ficam* (só Tier-1), por marca:

```bash
python manage.py shell -c "
from chips.models import KnownPart
from chips.engine import _match_family, _result_from_family, _CAP_RE, _CONFIRMED_CONFIDENCE
from collections import Counter
def H(v): return bool((v or '').strip())
fix=Counter(); res=Counter(); tot=0
for kp in KnownPart.objects.filter(confidence__in=_CONFIRMED_CONFIDENCE, review_status='approved').select_related('brand','family'):
    fam=kp.family or _match_family(kp.part_number)
    emcp=(fam.is_emcp if fam else False) or (kp.chip_type or '').lower() in ('emcp','umcp')
    idonly=(not(H(kp.emcp_ram) or H(kp.emcp_nand))) if emcp else (not(H(kp.capacity) or H(kp.density_gbit)))
    if not idonly: continue
    tot+=1
    r=_result_from_family(kp.part_number, fam) if fam else {}
    if fam and fam.is_emcp: ok=bool(_CAP_RE.search(str(r.get('emcp_ram') or '')) and _CAP_RE.search(str(r.get('emcp_nand') or '')))
    elif fam: ok=bool(_CAP_RE.search(str(r.get('capacity') or r.get('dram_density') or '')))
    else: ok=False
    (fix if ok else res)[kp.brand.name]+=1
print('IDENTITY-ONLY:', tot); print('BACKFILL alcança:', sum(fix.values()), dict(fix)); print('FICAM (Tier-1):', sum(res.values()), dict(res))
"
```

**A construir (próximo passo prático):** o script-irmão que quebra os **799 Micron** por `chip_type`
/ tem-família / PN em formato raw (hífen/espaço) — decide quanto é recuperável barato
(re-`fill_capacity_from_micron_api`, normalização de PN) vs datasheet manual.

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
- **Caso N1 (2026-07-09) — distribuidor é câmara de eco.** Três distribuidores (yoycart/Preduo/
  Alibaba) "concordavam" 1.5GB pro `KMQN10006`; a **leitura do chip físico na esteira provou 1GB**.
  Eles ecoam o mesmo erro entre si — *"3 fontes batendo" NÃO é confirmação se as 3 são distribuidor*.
  Reforça a hierarquia: **chip físico > datasheet Tier-1 > distribuidor**; broker é lista de
  descoberta, nunca spec. (Também vindicou reverter o remodel KMQ que se apoiava no 1.5GB errado.)
- **Backfill ≠ confirmação (2026-07-09).** Gravar o valor da gramática dentro de um registro e mantê-lo
  `confirmed` não adiciona verificação — e congelaria um bug de gramática como se fosse ouro. Ver §1.2.
- **Bug de dado ABERTO (2026-07-09): `ChipFamily.reasoning` do prefix `H9DP` com JSON inválido.** O
  script de §3.1 cuspiu `JSON inválido em ChipFamily.reasoning para prefix=H9DP` (sobra do fix LPDDR1 da
  SK Hynix). Não afeta contagem nem engine, mas **corrigir no `chips/knowledge/hynix.yaml`** (via chat SK).

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

## 6. ORDEM DE ATAQUE recomendada (atualizada 2026-07-09)

1. **Regra no portão** (Problema A, §1.4-1) — pequena, estanca a criação de novos confirmados-vazios.
   Decidir a exceção FBGA (status `identity`) com o dono. Resolve a **desonestidade do rótulo** sozinha.
2. **Micron 799 — o buraco real** (Problema A, §1.4-2). Primeiro o script de triagem (§3.1) pra separar
   recuperável-barato (re-`fill_capacity_from_micron_api` / PN raw) de datasheet-manual. Depois pesquisa
   Tier-1 do resíduo, priorizada por rentabilidade. **É aqui que o trabalho vale.**
3. **Samsung 17 sem-família** (Problema A) — resíduo pequeno, mesma pesquisa Tier-1.
4. **LPDDR3 por-família** (Problema B, §2) — construir da fonte-banco, com Octopart do dono nos códigos
   de distribuidor. Fluxo INVERTIDO (não rodar `correct`). Lição N1 reforça: chip físico > distribuidor.
5. **Os 61 grammar-covered** — baixa prioridade (já exibem certo; Tier-1 = só procedência). **Sem backfill.**
6. Legadas (KMJ/KMK/KML/KMV/KMS) e KM1 — menor prioridade.

> ~~Backfill (gramática → registro)~~ **RISCADO** como estratégia de confirmação (§1.2): não confirma
> nada e congelaria bugs de gramática. Substituído por **Tier-1 por PN**.
>
> Ao terminar: dobrar o durável (regra do portão + "confirmado confirma identidade, não spec, no
> identity-only") no `CLAUDE.md` e **apagar este arquivo**.
