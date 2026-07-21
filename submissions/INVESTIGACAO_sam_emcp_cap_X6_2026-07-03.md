# Investigação — SAM_EMCP_CAP, chave 'X6' (2026-07-03)

> Achado ao pesquisar known_parts para KMDD6001BM (família KMD). Guardado aqui
> para o chat que for corrigir isto — **não é um typo simples**, é mais complexo
> do que pareceu na primeira vista. Ver decisão do dono: investigar e documentar
> agora, corrigir em outra sessão.

## O que está no yaml hoje

`chips/knowledge/samsung.yaml`, mapa `SAM_EMCP_CAP`, linha 164:
```yaml
- [X6, 32GB, 2GB]
```
Esse mapa é **compartilhado** por praticamente todas as famílias eMCP/uMCP
(`decode_cap_map: SAM_EMCP_CAP`): KMD, KMF, KMG, KML, KMN, KM3P, KM4, KM5, KM8,
KMAG, KMAS, KM1, entre outras. A key `X6` vem de `pn[3:5]` — não é específica
de uma família.

## Evidência coletada (3 famílias, 3 fontes independentes)

| PN | Família (geração RAM) | Fonte | NAND | RAM |
|---|---|---|---|---|
| **KMDX60018M-B425** | KMD (LPDDR4X) | Octopart, título próprio (fetch direto: `octopart.com/part/samsung/KMDX60018M-B425`) — *"eMCP 32GB eMMC5.1 + 24Gb LPDDR4X-4266"* | 32GB | **24Gb = 3GB** |
| **KMGX6001BA-B514** | KMG (LPDDR3) | Múltiplos distribuidores independentes (Polaris/pmspte, Indasina, ScmHtai, Neview) — *"32GB eMMC 5.1 + 24Gb (3GB) LPDDR3"* | 32GB | **24Gb = 3GB** |
| **KM4X6001KM-B321** | KM4 (LPDDR4) | Avaq, fetch direto (`avaq.com/chip/km4x6001km-b321`) — *"combining 32GB eMMC5.1 and 16Gb LPDDR4-4266 RAM"* | 32GB | **16Gb = 2GB** |

## Por que isso NÃO é um fix de uma linha

Duas famílias (KMD, KMG) confirmam **3GB** para a key `X6`. Uma família (KM4)
confirma **2GB** — e esse 2GB bate exatamente com o valor atual do yaml **e**
com o próprio comentário `tip` da família KM4 ("ex: X6=32GB+2GB"), ou seja, o
KM4 provavelmente foi documentado corretamente na origem.

**Conclusão:** a mesma chave de 2 caracteres (`X6`) parece significar
capacidades de RAM DIFERENTES dependendo da família/geração que a usa. A
premissa do mapa compartilhado (uma key → sempre o mesmo par NAND+RAM,
independente de quem chama) **não vale** para essa chave — e possivelmente
para outras. Simplesmente mudar `X6` para `32GB+3GB` no mapa global **corrigiria
KMD/KMG mas quebraria o KM4** (que hoje está certo).

## O que ainda falta (para quem for corrigir)

- Não auditei as OUTRAS ~50 chaves do `SAM_EMCP_CAP` — só testei `X6`. Pode
  haver mais colisões do mesmo tipo (mesma key, famílias diferentes, valores
  reais diferentes).
- Uma correção real provavelmente precisa de mapas **por família ou por
  geração de RAM** (ex.: `SAM_EMCP_CAP_LPDDR4` vs `SAM_EMCP_CAP_LPDDR3`), não
  um único mapa global — mudança estrutural, não just um valor.
- Vale conferir se `decode_cap_map` já suporta apontar para mapas diferentes
  por família (a princípio sim, é só uma string por família em
  `chips/knowledge/samsung.yaml` — o que falta é CRIAR os mapas separados e
  redistribuir as ~50 chaves entre eles, conferindo cada uma).

## Addendum 2026-07-06 — mesma chave, mesma família, PN diferente

Achado novo, categoria diferente do X6/V8 (que era "mesma chave, família
diferente"): dentro do **próprio KMD**, a chave `P6` está confirmada em **4GB**
para `KMDP6001DA` (múltiplos distribuidores) mas o dono confirmou **3GB** para
`KMDP60018M` (Puris, Octopart não lista) — mesma chave `P6`, mesma família
KMD, PNs diferentes. O golden atual (`chips/tests.py::_SAM_GOLDEN`) ainda
assume 4GB pra qualquer P6 do KMD (herdado do fix de 04/07). Os dois
known_parts já corrigem a exibição individualmente (autoridade vence
gramática), mas o golden/mapa não capturam essa divergência — se aparecerem
mais casos assim, `decode_cap_map` por 2 chars pode não ser granular o
suficiente pra família KMD especificamente. Não investiguei mais fundo — só
documentando pro próximo fix.

## O que NÃO precisa de correção

As submissões de known_parts de hoje (`samsung_kmd_2026-07-03.yaml`) **não
dependem do mapa** — `KMDX60018M` foi sourced diretamente (Octopart,
específico daquele PN), então está correto independente deste problema
estrutural mais amplo.

## Addendum 2026-07-09 — chave 'N1' (falso alarme, corrigido no mesmo dia) + '31' (colisão KMF×KMQ) + E6/X6/D6/E1/82 (auditoria)

Achado ao pesquisar `KMQN10006A` (família KMQ, não encontrado na busca), depois
expandido a pedido do dono pra varrer a família toda.

### N1 — FALSO ALARME. Retratado no mesmo dia (ver abaixo)

Primeira leitura (mais cedo em 2026-07-09): concluí, com base em 3 fontes web
(yoycart "1.5G+8G" explícito, Preduo "Density: 8+12", Alibaba "8gb+12gb") +
cruzamento com specs de aparelho (Galaxy J5/J3, GSMArena, RAM 1.5GB), que o
mapa `[N1, 8GB, 1GB]` (linha 147) estava errado — RAM real seria 1.5GB.
Cheguei a submeter `KMQN10006A/M/B` como known_parts com 1.5GB.

**Corrigido depois, no mesmo dia, ao checar dados locais que eu não tinha
olhado antes de sair pesquisar na web** (`seed_known_parts.json`, known_parts
de sessões anteriores): a chave 'N1' já tinha **2 confirmações FÍSICAS
independentes** — chip lido na esteira da eMiner, não listagem de site:

| PN | Família | Fonte | Resultado |
|---|---|---|---|
| `KMQN10006B` | KMQ | Nota: "Chip físico confirmado na esteira (eMiner 2026-05-13)" | 8GB+**1GB** |
| `KMFN10012A-B214` | KMF (mesma chave 'N1') | Nota da KMQN10006B: "Segunda confirmação física (KMFN10012A-B214 era a primeira)" | 8GB+**1GB** |

Duas leituras físicas, duas famílias diferentes, mesmo resultado: **1GB**,
batendo com o mapa. As 3 fontes web provavelmente são o mesmo erro
propagado entre distribuidores (padrão já visto no projeto — distribuidor
"confunde Gb/GB, aluciona capacidade"). **Retirei o "conserto" de
`samsung_kmq_2026-07-09.yaml`** — a chave `N1` NÃO tem bug. O arquivo agora
só registra `KMQN10006A/M` como known_parts (pra sumir o "não achou"), com
o valor 1GB que a gramática já calculava certo.

**Lição pra próxima vez:** checar `seed_known_parts.json` / CSVs locais
(`data/psg/`) ANTES de sair pra pesquisa web nova — é bem possível que outra
sessão já tenha resolvido a mesma chave com fonte melhor (leitura física >
distribuidor). Achado corrigido rápido porque o dono pediu pra eu conferir
"o banco" antes de fechar, mas o ideal é essa ordem ser o padrão, não a
exceção.

### E6, X6, D6, E1, 82 — auditados via CSV local (Samsung Semiconductor Global), TODOS batem com o mapa

`data/psg/samsung_global_emcp_lpddr3.csv` (import local, fonte declarada
"Samsung Semiconductor Global", `confidence=confirmed`) já cobre várias
chaves KMQ. Resultado da auditoria (pedida pelo dono, que suspeitava X6=3GB
como no KMG — **não confirmado**, ver abaixo):

| Chave | PN de exemplo | NAND | RAM (CSV local) | RAM (mapa `SAM_EMCP_CAP` hoje) | Diverge? |
|---|---|---|---|---|---|
| `X6` | KMQX60013A-B419 | 32GB | 2GB (nota do CSV tem typo "pn[3:5]=X1", mas o PN decodifica X6) | 2GB (linha 164) | **NÃO** |
| `E6` | KMQE60013M/B-B318 | 16GB | 2GB | 2GB (linha 130) | **NÃO** |
| `E1` | KMQE10013M-B318 | 16GB | 2GB | 2GB (linha 129) | **NÃO** |
| `D6` | KMQD60013M-B318 | 32GB | 3GB (+ chip físico esteira 2026-05-13) | 3GB (linha 128) | **NÃO** |
| `82` | KMQ820013M-B419 | 16GB | 2GB (Preduo "16+16" + igual KMR820001M) | 2GB (linha 122) | **NÃO** |

**Suspeita do dono não se confirmou:** ao contrário do KMG (onde X6=3GB,
achado na investigação original acima), no KMQ a chave X6 aparenta ser
mesmo 2GB — mesma subtype LPDDR3 nas duas famílias, mas comportamento
diferente na mesma chave (o que, ironicamente, É o padrão do bug X6 — só
que aqui o mapaship com o valor certo pro KMQ, não pro KMG). Confiança
"distributor/CSV local", não datasheet direto — se quiser uma segunda fonte
pro X6 especificamente, ainda não tenho.

### 31 — colisão real, JÁ MAPEADA em 3 valores (mais complexa do que eu tinha achado)

Achado antes hoje: `KMF310012M-B305` (Preduo "16+8"→1GB) vs `KMQ310006A-B419`
(Preduo "16+12"→1.5GB) — colisão entre famílias. Checando
`seed_known_parts.json`, a chave `31` é AINDA mais granular — dentro do
PRÓPRIO KMQ, o mesmo par de caracteres já tem **3 valores reais
diferentes** dependendo do PN completo:

| PN | RAM real | Fonte |
|---|---|---|
| `KMQ310013B` | 1GB | físico (citado nas notas dos outros 2) |
| `KMQ310006A` / `KMQ310006B` | 1.5GB | samsungparts.com + Galaxy J3 SM-J327A service manual |
| `KMQ310013M` | 2GB | Alibaba "16gb+16gb 32dram" |

Isso já está coberto por known_parts em `seed_known_parts.json` (não
precisa de ação minha) — mas prova que, pra chave `31` do KMQ, os 2
caracteres não são granulares o suficiente NEM POR FAMÍLIA — variam por PN
individual. Mapa por-família (como KMD/KMG já têm) resolveria X6/E6/D6/E1/82
de uma vez, mas NÃO resolveria sozinho a `31` — essa precisaria de known_part
por PN mesmo, igual ao caso P6/KMD já documentado acima.

### Resumo prático pro dono

- `data/psg/samsung_global_emcp_lpddr3.csv` tem dados Samsung-sourced pra
  KMQ (D6, E1, E6, X6/X1-typo) que talvez ainda não tenham passado por
  `import_samsung_psg` — vale rodar se ainda não rodou, resolve 4 chaves de
  uma vez sem precisar de known_parts manual.
- `seed_known_parts.json` já tem 7 known_parts de KMQ de sessões anteriores
  (310006A/B, 310013M, 7X000SA, 820013M, D60013M, N10006B) — se ainda não
  estão em produção, vale conferir/gap-fill (`restore_known_parts` ou
  reconferir no admin).

### 31 — colisão real entre famílias (igual ao X6 original)

Aqui SIM é o padrão X6: mesma chave, famílias diferentes, valores
DIFERENTES — e uma delas bate com o mapa atual, a outra não.

| PN | Família | Fonte | NAND | RAM (campo Preduo) |
|---|---|---|---|---|
| `KMF310012M-B305` | KMF (LPDDR3) | Preduo (kmf310012m-b305) | 16GB | "16+**8**" → 8Gb=**1GB** — bate com o mapa atual |
| `KMQ310006A-B419` | KMQ (LPDDR3) | Preduo (kmq310006a-b419) | 16GB | "16+**12**" → 12Gb=**1.5GB** — diverge do mapa |

Mapa hoje: `['31', 16GB, 1GB]` (linha 114) — correto pra KMF, aparentemente
errado pra KMQ. **Não submeti `KMQ310006A` como known_part** — só uma fonte
estruturada (Preduo), sem confirmação por device/segunda fonte independente
como consegui pra N1 (a única pista de aparelho que achei foi um fórum de
reparo de LK K10, que não é o OEM — não conta como confirmação). Fica em
aberto: precisa de mais uma fonte antes de decidir, ou o dono decide se o
padrão Preduo (já provado consistente em ~6 PNs diferentes nesta e na
investigação original) é confiança suficiente.

### Implicação estrutural

Duas chaves (`X6`, `31`) já comprovadamente colidem entre famílias no mesmo
mapa `SAM_EMCP_CAP` compartilhado, mais uma chave (`N1`) com valor
simplesmente errado pra todo mundo que a usa. Reforça a recomendação original
de baixo: famílias ainda no mapa compartilhado (`KM`, `KM1`, `KMF`, `KMQ`,
`KMR`, `KMJ`, `KMK`, `KML`, `KMN`, `KMS`, `KMV`) são candidatas a migrar pra
mapas por-família, igual já foi feito pra KMD/KMG/KM4/KM5/KM8/KM2-family/
KMAG/KMAS.
