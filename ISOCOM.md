> ⚠️ **DUAS TRILHAS (Opção 2).** A **GRAMÁTICA** da ISOCOM (famílias + decode maps) vai morar em
> **`chips/knowledge/isocom.yaml`** (via `load_brands --brand isocom`) — **ainda não existe** (marca em
> onboarding, zero precedente — nem sequer citada em `PROMPT_PRECOS.md`, ao contrário de ISSI/Rayson/
> PieceMakers/GigaDevice/ESMT/Winbond, que já apareciam lá como "marca sem aba própria"). Os
> **known_parts** (PNs confirmados = autoridade) **não vão no yaml** — vivem no **banco**, submetidos
> por `submit_known_parts` e **aprovados pelo dono** no admin (four-eyes). **Processo obrigatório
> completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — não reproduz dado (isso vai viver no yaml e no banco, quando
> existirem). Aqui ficam: **convenções, o processo de pesquisa/submissão, anatomia do PN, armadilhas,
> rentabilidade (princípio), fontes, o *porquê*** e ponteiros — modelo estrutural: `SK_HYNIX.md`
> (referência de formato pedida pelo dono) e `ISSI.md` (precedente mais próximo: mesma situação exata —
> marca 100% nova, mesmo pedido do dono: ler `CLAUDE.md` inteiro + `SK_HYNIX.md` como referência e gerar
> o `.md` com base nas convenções/padrões/obrigações encontradas).
>
> ⚠️ **Estado em 2026-09-01: marca 100% nova, e mais nova que qualquer precedente no repositório.** Zero
> `chips/knowledge/isocom.yaml`, zero known_parts, zero família pesquisada, zero menção em qualquer outro
> `.md` do projeto (conferido nesta sessão: `grep -il isocom *.md` não retorna nada — nem o
> `PROMPT_PRECOS.md`, que já citava ISSI/Rayson/PieceMakers/GigaDevice/ESMT/Winbond como "marca sem aba
> própria" de preço). **Este documento é só o framework de processo** — a pesquisa real de PNs ISOCOM
> começa na próxima sessão/mensagem. §3.2/§4 ficam como esqueleto/placeholder de propósito. **A pergunta
> mais fundamental do documento — o que a ISOCOM fabrica — avançou muito em 2026-09-01: o dono pediu
> pesquisa do PN real `MEMA032G` e, com a confirmação física dele (pacote BGA; "ISOCOM" e "MEMA032G"
> impressos no próprio chip), a evidência aponta fortemente pra Hipótese B — ver §3.1 pro relato
> completo. Ainda NÃO confirmados: capacidade real, protocolo exato e a empresa por trás da marca.**

---

# ISOCOM.md — Guia Técnico e de Negócio (marca em onboarding)

> Em conflito, o **código é a fonte da verdade** (`chips/engine.py`, `chips/chip_types.py`). Quando
> `chips/knowledge/isocom.yaml` existir, ele também manda sobre este texto. Regras gerais do WTC:
> `CLAUDE.md`.

**ISOCOM** entra no WTC como marca nova, na mesma tradição de toda marca "11ª+" que `AUTORIA.md §9`/
`CLAUDE.md §5` já preveem: basta criar `chips/knowledge/isocom.yaml` que o `load_brands`/`deploy_catalog`
a descobre sozinho (glob), sem nenhuma configuração extra — todas as travas (portão, dedup, guards,
handshake, golden, tripwire) já valem pra ela desde já. Hoje existem **12** `chips/knowledge/*.yaml`
carregados (ESMT, Foresee, GigaDevice, SK Hynix, Kingston, Micron, Nanya, PieceMakers, Rayson, Samsung,
SanDisk, Toshiba-Kioxia) mais marcas em onboarding com `.md` mas ainda sem gramática. A ISOCOM entra
exatamente nesse mesmo ponto de partida.

⚠️ **Nota de 2026-09-01 (auditoria):** este censo envelhece rápido — a **Winbond** ganhou um
`chips/knowledge/winbond.yaml` no mesmo dia (bloco `brand` apenas, ZERO famílias, criado só para
destravar a Trilha B: o `submit_known_parts` exige a `Brand` no banco já no dry-run). Se a ISOCOM
precisar do mesmo destravamento antes de ter qualquer família confirmada, **esse é o precedente a
seguir** — yaml com `brand` e nada mais, nunca famílias inventadas para "ter alguma coisa".
Não confie neste parágrafo como censo: rode `ls chips/knowledge/*.yaml` na hora.

**⚠️ ATUALIZADO 2026-09-01 (tarde) — o que "ISOCOM" significa aqui teve avanço real, ver §3.1 pro
relato completo.** A hipótese inicial (mantida abaixo por registro histórico) era que "ISOCOM" pudesse
ser a **Isocom Components** internacionalmente conhecida — fabricante britânico de optoacopladores/
optoisoladores, fototransistores, emissores infravermelhos, displays de LED, transistores/diodos
discretos, sem relação nenhuma com memória. **A pesquisa do primeiro PN real (`MEMA032G`, pedido pelo
dono) contradisse essa hipótese:** o catálogo oficial da Isocom Components (60 págs, conferido na
íntegra) e o site oficial (`isocom.com`) não citam "MEMA" em lugar nenhum, e o chip físico que o dono
tem na bancada — confirmado por ele — é pacote **BGA** com "ISOCOM" e "MEMA032G" impressos, batendo com
padrão de memória (a família MEMA016G/032G/064G segue a progressão clássica 16/32/64 de capacidade em
GB). **Conclusão provisória: ISOCOM aqui é uma marca DIFERENTE da Isocom Components optoeletrônica —
provavelmente ligada a memória** (eMMC é a hipótese mais provável dado BGA + contexto de tablets/TV
boxes Android baratos), **mas nenhum datasheet de fabricante foi encontrado** — capacidade e protocolo
exatos ainda não são Tier-1. A convenção de campos deste documento (pensada pra memória) portanto
**deve se aplicar**, ao contrário do que a hipótese inicial temia — mas sem inventar capacidade/
protocolo antes de confirmar. **Ver §3.1 para o relato completo da investigação.**

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/isocom.yaml   ← GRAMÁTICA (famílias + decode maps). AINDA NÃO EXISTE (Opção 2: só gramática).
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml). Zero ainda.
AUTORIA.md / CLAUDE.md §5     ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
chips/chip_types.py           ← vocabulário de chip_type — conferido nesta sessão (2026-09-01): cobre
                                 DRAM/eMMC/UFS/eMCP/uMCP/NAND/SSD + uma dúzia de tipos "catálogo"
                                 (SRAM, NOR Flash, SoC, PMIC, Sensor, Mask ROM…) mas NENHUM cobre
                                 optoacoplador/semicondutor discreto — relevante só se a Hipótese A do
                                 §3.1 se confirmar (ver §5).
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → criar/editar
`chips/knowledge/isocom.yaml` → `load_brands --brand isocom` (dry-run = portão) → o **dono** roda
`--commit`. **known_parts** (autoridade) → arquivo de submissão → `submit_known_parts` (dry-run) → o
**dono** roda `--commit` + **aprova no admin**. ⚠ **Toda família da ISOCOM será "nova"** (a marca não
tem baseline grandfathered) → **PN-âncora no golden é OBRIGATÓRIO**, sem exceção
(`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:** `chips/engine.py`, `estoque/views.py`
(globais), yamls/known_parts de outra marca, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Eu (chat) edito arquivos. O dono roda os comandos que escrevem no banco.** Nunca `load_brands
   --commit` / `submit_known_parts --commit` / `migrate` — meu sandbox é isolado e não alcança o banco
   dele; meu papel é entregar o yaml/arquivo de submissão validado (dry-run passou), nunca gravar.
2. **Antes de qualquer prefixo: confirmar O QUE a ISOCOM fabrica (§3.1).** Duas hipóteses de mercado
   (optoeletrônica/discreto vs. memória/outra coisa) levam a arquiteturas de gramática **diferentes**.
   Não presumir por semelhança com nenhuma marca já onboardada — todas são memória/storage/SoC; a
   ISOCOM pode não ser nada disso.
3. **`load_brands --brand isocom` (dry-run) é o portão** da gramática — valida a convenção, nada é
   gravado. `submit_known_parts <arquivo>` (dry-run) é o portão dos known_parts. ⚠ **Verificado
   diretamente no código nesta sessão** (`submit_known_parts.py`: `Brand.objects.filter(name=brand_name)
   .first()` roda incondicionalmente — em dry-run e em `--commit`, ANTES de qualquer confronto com o
   banco): a marca **"ISOCOM" precisa existir no banco** (isto é, `load_brands --brand isocom --commit`
   já ter rodado, mesmo só local) **antes** de eu conseguir validar qualquer arquivo de submissão de
   known_parts, mesmo em dry-run — senão o comando levanta `CommandError` sugerindo "crie a gramática
   antes" (com sugestão de nomes parecidos, pra não confundir com erro de grafia). **Trilha A destrava
   Trilha B**, vale pra qualquer marca nova, ISOCOM inclusa.
4. **OPÇÃO 1 — SE a ISOCOM confirmar linha de DRAM discreta** (a confirmar, não presumir — §3.1): a
   GERAÇÃO vai no `chip_type` (ex. `chip_type="DDR3"`), nunca `"RAM"`/`"DDR"` genérico (família ativa
   com tipo genérico é **rejeitada** pelo portão). Espelhar no `subtype`. Memória gerenciada (eMMC/UFS/
   eMCP/uMCP), se houver, mantém `chip_type` como o tipo; `subtype` = geração LPDDR ou célula NAND.
   Fonte única: `chips/chip_types.py`.
5. **`subtype` = SÓ geração/célula**, 1–3 palavras — isto vale SE a linha for memória. ❌ densidade, bus
   width, tensão, "Industrial", "Mobile", nome comercial, qualificador de package.
6. **`interface`** = bus width (`x8`/`x16`/`x4`) para DDR/SDRAM discreto, lido da posição real do PN;
   vazio para LPDDR standalone e eMCP/uMCP — SE aplicável. Nunca a geração de RAM no `interface`.
7. **Se existir eMCP/uMCP** (a confirmar, improvável pelo perfil de mercado da Hipótese A do §3.1):
   `emcp_ram` = tipo ANTES da capacidade (`"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`); `emcp_nand` = só GB.
8. **Nunca inverta `val_primary`/`val_secondary`** nos decode maps — quando o mapa já existir, siga o
   padrão das linhas dele. Nunca escreva `"por die"` no secondary (o engine já anexa).
   `decode_density_type` e `decode_cap_map` são **mutuamente exclusivos** na mesma família (o portão
   rejeita os dois juntos).
9. **Não confie em distribuidor/IA sem verificar.** Erram Gb/GB, invertem primary/secondary, alucinam
   capacidade — e, se a Hipótese A se confirmar, também confundem specs de optoacoplador (CTR, tensão de
   isolamento, package) com as de memória. Cruzar sempre com datasheet oficial / Octopart (categorização
   própria, não a descrição do distribuidor dentro dele).
10. **⚠️ Ouro = IDENTIDADE, não as specs derivadas — atestar SEMPRE em Tier-1.** Um
    `confidence="confirmed"` verifica que o PN/marcação física é real; specs derivadas (capacidade,
    subtype, geração — se memória) podem estar erradas mesmo assim — foi o erro `MT52L=LPDDR4` da Micron
    (era LPDDR3) e o `H9DA`≠LPDDR3 da SK Hynix: geração por prefixo/nome sem atestar é o modo de falha
    nº1 do projeto inteiro. **A ISOCOM não tem nenhum precedente confirmado ainda — nem sequer o TIPO de
    produto está confirmado (§3.1) — toda família é a "primeira vez" num grau mais literal que qualquer
    marca anterior. Redobre o cuidado.**
11. **Só a MINHA marca (ISOCOM).** Não coletar/editar PN, família ou mapa de outra marca; nunca tocar em
    mapa global (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung); nunca reusar uma chave de posição de outra
    marca "porque parece igual" (foi a causa raiz do bug X6 da Samsung) — nem assumir que a mesma chave
    vale o mesmo dentro da própria família sem checar mais de um PN confirmado.
12. **PN ambíguo, tipo-lixo ou módulo → NUNCA decido sozinho.** Paro e pergunto ao dono. Nenhuma
    heurística substitui a palavra do dono sobre o que a peça realmente é — vale em dobro aqui, dado que
    nem a categoria de produto está fechada.
13. **Spec essencial (capacidade/CTR/tensão/tipo — o que quer que se confirme ser essencial) não
    confirmável em Tier-1 → EXCLUIR o PN da submissão inteiramente.** Nunca campo em branco, genérico ou
    estimado "pra documentar proveniência" — regra sem exceção, mesmo para tipo catálogo onde a
    capacidade não muda o veredito de rentabilidade. Documentar a tentativa/beco-sem-saída no rodapé
    "NÃO submetidos". ⚠️ **CORREÇÃO 2026-09-01: esta regra é DISCIPLINA, não trava — o portão NÃO a
    aplica.** O `KnownPartSpec` declara `capacity: str = ""` e o dry-run aprova um PN sem capacidade
    sem reclamar (conferido em `chips/knowledge/schema.py`). Não há rede aqui: se eu submeter
    incompleto, entra incompleto — a única barreira sou eu.
14. **Escopo é só dado (yaml da ISOCOM + arquivos de submissão).** Não editar `.py`/testes/infra/scripts
    sem pedido explícito do dono, mesmo que pareça um ajuste pequeno — se a mudança reclassifica algo que
    um comentário/teste já sinaliza como decisão pendente do dono, é sinal de PARE e pergunte.
15. **Se eu delegar pesquisa a um sub-agente:** proibir explicitamente edição de arquivo no prompt dele —
    já houve incidente de sub-agente editando yaml de outra marca por engano (revertido, outra sessão).

### 0.3 Hierarquia de fontes (a confirmar/ajustar na prática — ainda sem nenhum precedente ISOCOM)

```
1. Site oficial + datasheet ISOCOM (domínio NÃO verificado nesta sessão — não presumir isocom.com ou
   qualquer outro sem checar) → Tier 1
2. Octopart / Nexar — categorização PRÓPRIA do Octopart, nunca a descrição do distribuidor dentro dele → Tier 2
3. Alldatasheet / LCSC / DigiKey / Mouser com rastreabilidade ISOCOM → Tier 2
4. Distribuidor B2B rastreável (Preduo, WinSource, Jotrin…) → só apoio; nunca rebaixa um confirmed;
   nunca decide capacidade/spec principal sozinho
5. iFixit/GSMArena → chip_type confirmado por inspeção física (device teardown) — mais plausível aqui do
   que nas marcas de memória puras, se a Hipótese A (discreto/optoeletrônica em PCB) se confirmar
6. IA externa → ÚLTIMO RECURSO; verificar SEMPRE contra 1–3
```
Nunca fonte primária: fóruns, distribuidor sem rastreio, catálogos genéricos, eBay, IA sem verificação.
Regra geral do WTC (`CLAUDE.md §6`): fabricante/datasheet > Octopart/Nexar > distribuidor B2B rastreável
> Preduo > IA > especulação — importadores **nunca** rebaixam um registro `confirmed`/`manual`.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única: `chips/chip_types.py` (código).** Contexto geral: `CLAUDE.md §6`. A tabela
> abaixo é a convenção universal do WTC **para memória** — só se aplica à ISOCOM se a Hipótese A do
> §3.1 (optoeletrônica/discreto) for descartada. **Não presuma o perfil da marca antes da hora.**

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1–5 / SDRAM (se houver) | a geração (`DDR2`, `DDR3`…) ou `"SDRAM"` (legado, sempre NÃO RENTÁVEL) | espelha | bus width (`x8`/`x16`/`x4`) | `density_gbit` (Gb/die) |
| LPDDR standalone (se houver) | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| eMMC / UFS (se houver) | `"eMMC"`/`"UFS"` | `""` | versão (`"eMMC 5.1"` etc.) | `capacity` (GB) |
| eMCP / uMCP (se houver) | `"eMCP"`/`"uMCP"` | geração RAM | `""` | `emcp_nand` (GB) + `emcp_ram` (tipo+GB) |
| NAND Flash (raw, se houver) | `"NAND Flash"` | célula (`"SLC NAND"`/`"MLC NAND"`/`"TLC NAND"`) | — | `capacity` (bytes) |
| Catálogo (SRAM/NOR Flash/SoC/PMIC/Sensor/Mask ROM…) | o tipo específico | descritivo (chip_type MANDA, não normaliza) | — | sem caixa comercial (ver §5) |
| **Optoacoplador / discreto (Hipótese A, §3.1)** | **NÃO EXISTE no vocabulário hoje** (conferido em `chips/chip_types.py`, 2026-09-01) | — | — | — |

**Regras absolutas** (idênticas em todo o WTC, para o que for memória/catálogo já coberto): `subtype`
nunca carrega densidade/bus width/tensão/qualificador de mercado. `density_gbit` = Gb por die (campo do
`KnownPart`; `dram_density` é o derivado pelo engine — não confundir, `CLAUDE.md §6`). `capacity` =
pacote em bytes, nunca Gbit. `emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip`/`notes` = todo o
resto (tensão, velocidade, organização, avisos, proveniência).

**Label da caixa** (referência, mesmo padrão de todas as marcas — só se aplica a memória): DDR
`{subtype}+{density_gbit}G` · LPDDR `{chip_type}+{cap GB}G` · eMCP `EMCP{nand}+{ram}` · eMMC
`EMMC{cap}GB` · UFS `UFS{cap}GB` · NAND `{subtype}{capacity}`.

⚠️ **CORREÇÃO 2026-09-01 (auditoria do dono): `commercial=False` NÃO é lido por nada em produção.**
`is_commercial`/`COMMERCIAL_TYPES` existem só em `chips/chip_types.py` e em `chips/tests_convention.py`
— **zero** consumidores em `estoque/views.py` ou em `pricing/`. É a INTENÇÃO declarada do tipo, não um
comportamento implementado. Então "catálogo não tem caixa" é falso na prática: o que o gateway faz
é cair no ramo desconhecido e usar o **nome cru do `chip_type`** como etiqueta. Medido em 2026-09-01:

```
NOR Flash  cap='16MB'  → caixa='NOR Flash'  categoria='unknown'  kind='none'   NÃO RENTÁVEL
SRAM       cap='8MB'   → caixa='SRAM'       categoria='unknown'  kind='none'   INDETERMINADO
SoC        cap=''      → caixa='SoC'        categoria='unknown'  kind='none'   INDETERMINADO
```

Confirmado: os **11** tipos de categoria `catalog` (NOR Flash, OneNAND, MCP, ePoP, SoC, PMIC, Sensor,
SRAM, Mask ROM, NVMe SSD, BGA SSD) são todos `commercial=False` — a listagem do §5 está correta. O que
muda é a consequência: eles **são** roteados, para uma caixa `unknown` com o nome do tipo. Como o código
F12 é **eterno**, um tipo novo para optoacoplador ganharia uma gaveta chamada literalmente com o nome do
tipo, a não ser que o dono decida outra coisa **antes**. Não é decisão deste chat.

---

## 2. Processo de pesquisa e submissão — o COMO

### 2.1 Passo zero — antes da Trilha A (específico da ISOCOM, não existe nas outras marcas)

Antes de tocar em qualquer prefixo: resolver a pergunta do §3.1 com pelo menos uma fonte checável (site
oficial, datasheet, ou o chip físico que o dono tem na bancada — foto/inspeção já basta pra saber se é
um pacote de memória BGA ou um DIP/SOP de optoacoplador). **Só depois disso a Trilha A começa a fazer
sentido** — o formato do `isocom.yaml` (quais mapas, qual decode) depende inteiramente da resposta.

### 2.2 Trilha A — Gramática (família nova ou correção)

1. Confirmar o prefixo/família em fonte Tier-1 (§0.3) — **nunca** criar família por analogia estrutural
   sem fonte que nomeie o prefixo diretamente.
2. Editar/criar `chips/knowledge/isocom.yaml`: `brand` (`name` exato — provavelmente `"ISOCOM"`; `code`
   curto único — a confirmar com o dono, candidato natural `"ISOCOM"` já que o nome é curto), `maps`
   (tabelas `[char_key, val_primary, val_secondary]`, prefixo de mapa por legibilidade, ex.
   `ISOCOM_XXX_CAP` — a FK `brand` é quem realmente separa), `families` (a gramática posicional:
   `prefix`, `chip_type`/`subtype`/`interface`, `priority`, `pn_length`, `is_emcp`, `active`,
   `decode_cap_*`/`decode_gen_*`/`decode_density_type`, `suffix_rules`, `reasoning` com a fonte).
3. Rodar `python manage.py load_brands --brand isocom` (dry-run = portão) — resolver os erros até passar.
4. **Família nova → GOLDEN obrigatório:** entregar PN-âncora + saída esperada (tipo/subtipo/capacidade/
   **rentabilidade**, ou o que for o equivalente se não for memória) em `_ISOCOM_GOLDEN`
   (`chips/tests.py`). `GoldenObrigatorioTests` falha sem isso.
5. **Tipo novo em `chip_types.py`** — cenário **provável** aqui (ao contrário da maioria das marcas), se
   a Hipótese A do §3.1 se confirmar: declarar a regra de rentabilidade junto (`RentabilidadeHandshakeTests`
   falha sem) — decisão do **dono**, eu preparo a proposta mas não decido o limiar/veredito sozinho.
6. Rodar a suíte (`python manage.py test chips estoque --settings=core.settings_test`) +
   `characterize_baseline --diff` — só o pretendido deve mudar.
7. Entregar ao dono: diff do yaml + golden + saída dos testes. Ele roda `--commit` local, depois publica
   em prod (`git push` + `load_brands --brand isocom --commit` apontando o `DATABASE_URL` do Render).

### 2.3 Trilha B — Known_parts (autoridade — a que vence a gramática)

1. Pesquisa Tier-1 exaustiva por PN (não presumir por semelhança com PN "parecido").
2. Escrever o arquivo `submissions/isocom_<familia_ou_cluster>_<data>.yaml`: `part_number` + specs +
   `confidence` (`confirmed`/`manual`, ver regra de ouro #13 se algo essencial não confirma) + **`notes`
   com a fonte Tier-1 citável** (URL/nome do datasheet — sem fonte não vira `confirmed`/`manual`).
   ⚠ `brand:` no arquivo de submissão é **texto puro** (`brand: ISOCOM`), nunca o bloco `name`/`code`/
   `notes` — esse bloco é do yaml de gramática. Já mordeu a Kingston duas vezes (`AUTORIA.md §4`).
3. **Lembrete de sequência (achado verificado nesta sessão, §0 acima):** `submit_known_parts` só valida
   em dry-run se a `Brand` "ISOCOM" já existir no banco — ou seja, a Trilha A (mesmo que só `--commit`
   local, sem publicar em prod) precisa rodar pelo menos uma vez antes de eu conseguir validar QUALQUER
   submissão.
4. Validar: `python manage.py submit_known_parts <arquivo>.yaml` (dry-run = portão). Corrigir até passar.
5. **Entregar o arquivo validado ao dono** — eu NÃO rodo o `--commit` (sandbox isolado + regra de ouro
   #1). Comando que entrego: só `submit_known_parts <arquivo>.yaml --commit` — **sem `--user`**, mesma
   correção que o dono já fez na sessão ISSI (2026-07-10) apesar de o `AUTORIA.md` mencionar
   `--user <id-do-chat>` para four-eyes.
6. O dono roda o `--commit` (grava `submitted`, oculto) e **aprova no admin**
   (`/admin/chips/knownpart/`).
7. Só depois de aprovado o PN fica visível/autoritativo no engine.

### 2.4 Disciplina de pesquisa (como NÃO tropeçar — obrigações já aprendidas em outras marcas)

- **O objetivo é o BANCO de PNs confirmados, não a gramática.** "A gramática já decodifica esse PN
  certo" (`grammar_complete=true`, `confidence=estimated`) **nunca** é motivo pra pesquisar menos ou
  parar de buscar primos/irmãos — são dois problemas separados. Esta correção já se repetiu 3× em outras
  marcas do WTC (a última quase textual: *"esquece gramática, nosso objetivo é PN confirmado no banco de
  dados"*) — o sinal de alerta é o próprio raciocínio "seria autoridade redundante, não vale submeter":
  pare e submeta mesmo assim.
- **Pesquisar o CLUSTER inteiro, nunca 1 PN por rodada** — buscar site-wide e abrir/ler a fonte primária
  direto, nunca confiar só no resumo em prosa da busca.
- **Se a linha for memória, mostrar a aritmética Gb→GB sempre** que eu reportar uma capacidade — nunca
  só declarar "XGB confirmado". De preferência 2+ fontes independentes batendo, cada uma com a conta
  visível.
- **Listar os known_parts da submissão direto no chat** (PN + spec principal + confidence), além de
  entregar o arquivo — o dono confere em paralelo sem abrir o arquivo primeiro.
- **Toda entrega de known_parts vem com o comando pronto** (dry-run já rodado + `--commit`), mesmo se
  ainda houver pergunta/pendência na mesma mensagem.
- **Nunca reusar uma chave de posição assumindo que vale o mesmo valor em outra família** (ou até dentro
  da mesma família, em PNs/sufixos diferentes) — confirmar cada chave com PN âncora próprio.
- **Não é preciso pedir ao dono uma query manual de `part_number_norm` antes de bulk-submeter** — essa
  prática foi superada em 2026-08-17: o próprio `submit_known_parts <arquivo>` já confronta cada PN
  contra o banco em QUALQUER dry-run (confirmado nesta sessão lendo o código, §0.2 regra 3), classificando
  cada um em `NOVO`/`RESUBMETE`/`COMPLEMENTO`/`CONFLITO`/`IGUAL` (`AUTORIA.md §4.1`). Rodar o dry-run já É
  o precheck. Único cuidado: se aparecer `COMPLEMENTO`, a entrega ao dono TEM que incluir `--fill-empty`
  no comando de `--commit` — senão esses PNs são pulados de novo, em silêncio.
- **A lista de "fuzzy suggestions" de um debug já são KnownParts `approved`** — pesquisar/resubmeter um
  PN que já está lá é redundante. O alvo real é o PN NÃO identificado.
- **`submissions/isocom_*.yaml` SÃO versionados normalmente, junto com o(s) yaml(s) de gramática** — ao
  entregar comando de commit pro dono, o `git add` inclui os dois. Único artefato fora do git:
  `*.conflitos.yaml` (gerado pelo `resolve_conflicts`, output transitório, não autoral). **Checado nesta
  sessão contra duas fontes que DIVERGEM:** a memória de projeto registra essa regra como corrigida em
  2026-08-24 (verificação direta: `.gitignore` só ignora `*.conflitos.yaml`; `git log -- submissions/*.yaml`
  mostra dezenas de commits reais de outras marcas) — a versão anterior ("nunca vai pro git") estava
  invertida. **Porém** o docstring do próprio `submit_known_parts.py` (lido nesta sessão) ainda diz o
  oposto ("o arquivo é formulário de submissão... é consumido uma vez, não vai pro git, não re-sincroniza").
  Sigo a prática verificada empiricamente (memória, com evidência de `git log`) em vez do comentário no
  código, mas vale confirmar com o dono se o docstring está só desatualizado. Nunca criar cópia renomeada
  de um arquivo de submissão "pra não perder" — se precisar reformular, editar o arquivo original.
- **Doc de marca pode ser editado pelo dono direto no disco.** Antes de reescrever `ISOCOM.md` (este
  arquivo) numa sessão futura, reler o estado atual no disco — nunca confiar em cópia cacheada de sessão
  anterior; o dono já corrigiu outros `.md` de marca (RAYSON.md, ESMT.md) direto no disco mais de uma
  vez.
- **Se `AskUserQuestion` falhar** (erro de ferramenta): perguntar em texto normal no corpo da resposta é
  um fallback válido — não insistir na tool nem travar a conversa.

### 2.5 Checklist de handoff (resumo — completo em `AUTORIA.md §6`)

- [ ] Confirmei o que a ISOCOM fabrica (§2.1/§3.1) antes de propor qualquer prefixo.
- [ ] Só mexi na ISOCOM; não toquei em mapa global de outra marca.
- [ ] Nada inventado/estimado; ambíguo → perguntei ao dono; essencial não confirmado → excluí o PN.
- [ ] Gramática: `load_brands --brand isocom` (dry-run) passou; família nova → golden entregue.
- [ ] Tipo novo (provável, ver §5) → handshake de rentabilidade passa, e o veredito foi decisão do dono.
- [ ] Known_parts: cada um com fonte Tier-1 na `notes`; `submit_known_parts` (dry-run) passou; listei os
      PNs no chat; entreguei o arquivo + o comando (`--commit`, sem `--user`).
- [ ] Suíte inteira verde + `characterize_baseline --diff` só com o pretendido.
- [ ] Não toquei no banco do dono nem em prod; não editei `.py`/testes/infra sem pedir.

---

## 3. Anatomia do PN — como LER um chip ISOCOM

### 3.1 A pergunta em aberto: o que a ISOCOM fabrica — resolvida em parte em 2026-09-01 (NÃO é gramática — é o passo zero)

> **Atualização 2026-09-01:** a pesquisa do primeiro PN real (`MEMA032G`, pedido pelo dono) avançou esta
> pergunta de "duas hipóteses igualmente plausíveis" pra "Hipótese B favorecida com alta confiança,
> Hipótese A praticamente descartada para *esta* marca" — ver o relato completo abaixo. **Continuam
> não confirmados:** capacidade exata, protocolo exato, e a identidade da empresa por trás do nome
> "ISOCOM" nesta bancada. Nenhum known_part foi submetido ainda — regra de ouro #13 (spec essencial não
> confirmável em Tier-1 → excluir, nunca estimar).

**Hipótese A — Isocom Components (optoeletrônica):** fabricante britânico historicamente ligado a
optoacopladores/optoisoladores, fototransistores/fotodiodos, emissores infravermelhos, displays de LED
(7 segmentos), transistores e diodos discretos de pequeno sinal. **Contradita nesta sessão:** o catálogo
oficial da Isocom Components (PDF, 60 págs., lido na íntegra) e o site oficial `isocom.com` (buscado
nesta sessão) **não citam "MEMA" em lugar nenhum** — nem como prefixo de família, nem em qualquer lista
de produtos. Isso não prova que a empresa não exista ou não seja relevante a outros PNs futuros, mas
para o PN `MEMA032G` especificamente, a hipótese não se sustenta.

**Hipótese B — memória, identidade da empresa AGORA encontrada:** confirmada com alta confiança
nesta sessão (2 rodadas de pesquisa). Convergência de quatro pontos independentes:

1. **Ausência da Hipótese A** — catálogo oficial + site oficial da Isocom Components não citam "MEMA".
2. **Padrão de nomenclatura de memória** — `MEMA016G` / `MEMA032G` / `MEMA064G`, progressão clássica
   16/32/64 (dobrando), igual ao padrão que toda marca de memória do WTC já usa.
3. **Confirmação física do dono:** chip na bancada é **pacote BGA**, com **"ISOCOM" e "MEMA032G"
   impressos** no próprio chip.
4. **Identidade corporativa real, encontrada nesta 2ª rodada:** "ISOCOM" pra memória é marca da
   **Shenzhen Longsys Electronics Co., Ltd.** — a MESMA empresa dona da **Foresee** (já onboardada
   neste projeto, ver `foresee.yaml`/`FORESEE.md`) e da **Lexar**. Evidência: (a) pedido de marca
   USPTO serial `88496930`, depositado pela Longsys em 01/07/2019, classe 009, especificamente pra
   "Electronic chips...Integrated circuits; Semiconductor chips" (uso real) + "USB flash drives;
   Computer memory modules; SD Memory Cards; Solid state drives" (intenção de uso) — a PRÓPRIA
   Longsys declarou à USPTO que "ISOCOM" era pra produtos de memória; (b) caso TTAB nº `91256263`,
   **"Isocom Components 2004 Limited v. Shenzhen Longsys Electronics Co., Ltd."** — oposição da
   Isocom Components (a fabricante britânica de optoacopladores) em 09/06/2020, MANTIDA, com o pedido
   da Longsys **abandonado em 26/10/2020** (trademarkelite.com); (c) listagem agregada de marcas da
   Longsys (justia.com) confirma "ISOCOM" entre as ~31 marcas associadas à empresa, ao lado de
   LEXAR/FORESEE/LONGFORCE (todas reais e verificáveis).

   **Isso explica o mistério inteiro:** são duas empresas reais brigando pelo mesmo nome. A Isocom
   Components ganhou nos EUA (por isso o catálogo oficial dela não tem "MEMA"). A Longsys
   aparentemente continuou fabricando/exportando sob "ISOCOM" fora do registro americano (comum no
   ecossistema de Shenzhen quando a disputa não atinge outros mercados) — daí fábricas/distribuidores
   asiáticos (Alibaba, digipart, ic-components, ariat-tech) venderem os chips MEMA0xxG normalmente,
   enquanto a RS Components (distribuidor estruturado/autorizado, o mesmo usado como fonte
   `confirmed` em outras marcas deste projeto) só lista os optoacopladores genuínos da Isocom
   Components sob essa marca — **zero memória lá**, reforçando que são catálogos de fato diferentes.
   ⚠ Nuance honesta: o registro AMERICANO foi abandonado após a disputa — não é uma marca limpa/
   vitoriosa da Longsys nos EUA. Isso não muda a classificação técnica do chip, mas é a causa raiz da
   confusão de atribuição entre distribuidores.

**Protocolo — eMMC, com fonte (não mais só hipótese contextual):** dois anúncios de marketplace,
títulos verificados diretamente (`Alibaba`): `MEMA032G-Longbo-32GB-ISOCOM-eMMC-flash` e
`MEMA064G-M0S00-EMMC-64GB-153FBGA-Memory`. **Limitação honesta:** o corpo das duas páginas Alibaba
não renderizou via fetch automatizado (JS-heavy) — só os títulos dos anúncios foram verificados, não
uma ficha técnica completa. "Longbo" no primeiro título não foi identificado com certeza (provável
revendedor/trading company, não necessariamente quem fabrica). A versão JEDEC exata do eMMC (4.5,
5.0, 5.1...) **não foi encontrada em nenhuma fonte** — campo `interface` fica vazio nos known_parts
até alguém achar isso.

**O que ainda NÃO está confirmado, mesmo com a identidade e capacidade já sourced:**
- **MEMA016G** — o PN existe (visto em `ariat-tech.com`), mas nenhuma fonte mostra a capacidade dele
  especificamente (ao contrário de 032G e 064G, cada um confirmado por um título de anúncio próprio).
  Padrão sugere 16GB com força, mas **excluído da submissão** por regra de ouro #13 — sem fonte
  própria, não incluí só por analogia de família.
- **Versão JEDEC do eMMC** — ver acima.
- **Quem de fato fabrica o die NAND** — a Longsys é conhecida principalmente como empacotadora/
  integradora (igual a Foresee/Kingston fazem com NAND de terceiros), não necessariamente fab própria
  — não pesquisado nesta rodada, não essencial pra classificação.
- Bloqueios que seguem de pé: `ic-components.com`/`ariat-tech.com`/`allelcoelec.com` (Cloudflare/403
  pra buscas mais profundas), a página de teardown `reverse-costing.com/.../isocom_mema064g/` (403).

**Ação concreta tomada nesta sessão:** criado `submissions/isocom_mema_2026-09-01.yaml` com
`MEMA032G` (32GB) e `MEMA064G` (64GB), `chip_type: eMMC`, **`confidence: manual`** (não "confirmed" —
a fonte de capacidade é um único anúncio de marketplace por PN, mais forte que "sem fonte nenhuma"
mas mais fraco que o padrão de 3 fontes de engenharia cruzadas que este projeto usa pra `confirmed`;
ver cabeçalho do arquivo pro rationale completo). `MEMA016G` ficou de fora, documentado como exclusão
consciente. Comandos completos (Brand + known_parts) no corpo da mensagem desta sessão.

**Se uma sessão futura quiser subir a confiança pra `confirmed`:** datasheet real da Longsys (não
encontrado ainda em nenhuma busca), ou o dono testando/lendo o chip com programador/adaptador eMMC,
ou uma 2ª fonte estruturada (tipo LCSC/DigiKey/Octopart) confirmando os mesmos números — qualquer um
desses já bastaria pra promover de `manual` pra `confirmed`.

### 3.2 Estrutura do PN — famílias MEMA e MEMD, eMMC (gramática criada em 2026-09-01)

Duas famílias, capacidade LITERAL — mesma convenção da Foresee/Longsys (reforça a hipótese de mesma
fabricante, §3.1). **MEMA** é a forma CURTA, sem sufixo — a que aparece marcada fisicamente no chip
do dono:

```
MEMA 032 G
0123 456 7
```

**MEMD** espelha a estrutura FEMD da Foresee LETRA POR LETRA (prefixo 4 chars terminado em D, grade
de 2 chars, capacidade, "G", sufixo de order code):

```
MEMD NN 032 G -M1S07
0123 45 678 9 (sufixo não decodificado)
```

| PN | Capacidade | Fonte |
|---|---|---|
| MEMA016G | 16GB | Lista de fornecedores aprovados de eMMC da **Rockchip** (`RKeMMCSupportList`, `dl.radxa.com` — doc técnico de fabricante de SoC pra qualificação de hardware, não distribuidor/marketplace): `MEMA016G-M0T00`, 128Gb TLC×1, 3D, **eMMC 5.1**, FBGA 11.5×13mm. Também é o PN real escaneado no estoque do dono (`in_review_queue=true`). |
| MEMA032G | 32GB | Confirmação física do dono (chip fotografado: "ISOCOM"/"MEMA032G" impressos) + `digipart.com/part/MEMA032G` + título Alibaba (`MEMA032G-Longbo-32GB-ISOCOM-eMMC-flash`) + Rockchip (`MEMA032G-M0D01`, 256Gb TLC×1, 3D, **eMMC 5.1**, FBGA 11.5×13mm — mesma lista acima). |
| MEMA064G | 64GB | Título Alibaba (`MEMA064G-M0S00-EMMC-64GB-153FBGA-Memory`) — mesma marcação "M0S00" do chip físico do MEMA032G. |
| MEMDNN032G-M1S07 | 32GB | Rockchip (mesma lista): 256Gb TLC×1, 3D, eMMC 5.1, FBGA 11.5×13mm. |
| MEMDNN064G-M1D03 | 64GB | Rockchip (mesma lista): 512Gb TLC×1, 3D, eMMC 5.1, FBGA 11.5×13mm. |

Regra posicional (3 dígitos = GB) validada em pelo menos 5 PNs com fonte própria, ZERO
contra-exemplos, reforçada pelo fato de a Foresee (mesma dona provável, Longsys) usar exatamente essa
convenção em `FRS_EMMC_CAP` (`chips/knowledge/foresee.yaml`) — MEMD, em particular, reproduz a
estrutura FEMD inteira, não só a convenção de capacidade. Implementado em
`chips/knowledge/isocom.yaml`: `ISC_EMMC_CAP` (mapa compartilhado, `016`/`032`/`064`) — **não**
extrapolado pra `004`/`008`/`128`/`256` sem evidência direta; PNs com esses códigos ficam
INDETERMINADO até serem vistos numa fonte real.

⚠️ **Relação MEMA↔MEMD não confirmada.** `MEMA032G`/`MEMDNN032G-M1S07` (e o par 64GB) têm specs
IDÊNTICAS (capacidade, versão eMMC, arquitetura 3D TLC, tamanho de pacote) — podem ser o mesmo
produto sob dois nomes (curto/marcação física vs. order code completo do fabricante) ou dois SKUs
distintos com a mesma especificação comercial. Documentado como observação, não tratado como fato;
não afeta a classificação (cada PN decodifica corretamente pela sua própria família).

⚠️ O §6 tinha uma entrada dizendo que "2 known_parts não é suficiente pra generalizar gramática com
segurança" — revertida aqui não por generalizar especulativamente sobre os mesmos dados de antes, mas
porque um **PN real apareceu ao vivo** precisando de resolução agora (`MEMA016G`, escaneado no
estoque do dono, `in_review_queue=true`, o próprio fuzzy-match do engine já o associava aos outros
dois) — exatamente a condição que aquela entrada previa ("assim que houver PNs suficientes"). Uma 2ª
busca mais funda (feedback do dono, ver §8) achou a fonte Rockchip, que RESOLVEU `MEMA016G` de forma
independente (deixou de ser só aplicação mecânica da regra) e revelou a família-irmã MEMD de brinde.

⚠️ **Ainda não confirmado em Tier-1** (datasheet oficial da Longsys/fabricante): nenhuma fonte
encontrada até agora é do próprio fabricante — toda a base é lista de fornecedor aprovado (Rockchip,
terceiro) + distribuidor + confirmação física do dono + registro de marca (TTAB). Pin-count FBGA
exato do MEMA032G físico permanece sem confirmação numérica direta (Rockchip dá o tamanho do pacote,
11.5×13mm, não a contagem de pinos — o MEMA064G tem "153-Pin FBGA" via Alibaba, plausível pro mesmo
tamanho de pacote, mas não testado como regra geral).

**Atualização 2026-09-02 — `pn_length` da MEMD resolvido por evidência de campo:** debug de estoque
ao vivo capturou `MEMDNN064G` (10 chars, BARE, sem sufixo de order code), `in_review_queue=false` —
o engine já classificou certo via gramática (eMMC 64GB, ISOCOM, eMMC 5.1, RENTÁVEL) mesmo sem
known_part exato, porque a regra posicional (pn[6:9]=GB) não depende do sufixo. Essa é a primeira vez
que se vê a forma sem sufixo desta família na prática — resolve a lacuna que a família MEMD tinha
desde que foi criada ("não há confirmação física de como um chip MEMD é marcado de verdade", ver
`isocom.yaml`) e bate EXATAMENTE com o padrão já visto na MEMA (chip físico sem sufixo; o sufixo só
aparece no order code do distribuidor/Rockchip). `pn_length` da família MEMD atualizado de `null` pra
`10` — mesmo papel que o `pn_length=8` da MEMA já tinha, um aviso soft de "possivelmente truncado"
que nunca bloqueia PNs mais longos.

**Correção (mesmo dia):** inicialmente decidi NÃO criar known_part pra essa forma bare — julguei que a
única evidência era o próprio scan, sem fonte externa citável confirmando `MEMDNN064G` (sem sufixo)
como PN válido em si. O dono apontou o precedente certo: `MEMA016G` (ver §8, rodada 5) foi registrado
exatamente assim — capacidade herdada de uma entrada COM sufixo da mesma lista Rockchip
(`MEMA016G-M0T00`), traduzida pra forma bare porque a convenção de marcação física bare da família já
estava confirmada (MEMA032G físico, rodada 2). O scan desta rodada é exatamente essa mesma peça de
evidência que faltava pra MEMD. Criado `submissions/isocom_memd_2026-09-02.yaml` com `MEMDNN064G`
(64GB, eMMC 5.1, `confidence: distributor`, mesma fonte Rockchip do irmão `MEMDNN064G-M1D03`) —
`MEMDNN032G` bare NÃO incluído (só a forma 064G apareceu ao vivo até agora; mesma disciplina de só
submeter o que realmente foi visto).

---

## 4. Armadilhas e Decisões Arquiteturais

**[A PREENCHER]** — nenhuma armadilha ISOCOM-específica confirmada ainda. **Atenção:** se a Hipótese A
do §3.1 se confirmar, as armadilhas sistêmicas do WTC listadas abaixo (todas de domínio memória,
levantadas em `CLAUDE.md §7`) **podem simplesmente não se aplicar** — capacidade, Gb×GB, `emcp_*` não
existem em optoacoplador. As armadilhas reais desse domínio ainda não têm nenhum precedente no WTC e
precisarão ser levantadas do zero, na prática, com a primeira pesquisa. Enquanto a resposta ao §3.1 não
chega, de olho nas armadilhas sistêmicas **caso seja memória**:

- Unidade Gb×GB confundida (o erro mais comum do domínio inteiro).
- `decode_density_type` + `decode_cap_map` juntos na mesma família (mutuamente exclusivos).
- Tipo/geração morta retornando INDETERMINADO em vez de NÃO RENTÁVEL (checar geração ANTES de exigir
  capacidade) — também relevante fora de memória: um `chip_type` novo (catálogo) mal declarado no
  Handshake pode cair no mesmo buraco (`CLAUDE.md §7`, "padrão recorrente").
- `subtype` verboso vazando pro label da caixa (mitigado por `canonical_gen`, mas escrever limpo mesmo
  assim no write-time) — só se aplicável.
- Mesma chave de posição com valor diferente dentro da MESMA família — sempre checar mais de um PN
  confirmado por chave antes de assumir que ela generaliza.
- **⚠️ O portão NÃO barra unidade de BIT em `capacity`** (acrescentado na auditoria de 2026-09-01).
  `BYTE_ONLY_FIELDS` são só `emcp_ram`/`emcp_nand`. Medido: `capacity='1Gb'` **passa** e o
  `_extract_gib` lê **1.0 GB** — 8× a mais. Se a Hipótese B (memória) se confirmar e a ISOCOM nomear
  por bit (comuníssimo em NOR/NAND serial), a conversão `bits ÷ 8` é responsabilidade DESTE CHAT, com a
  aritmética escrita na `notes`. O portão não vai te salvar disso.
- **O `save()` reescreve parte do que foi submetido.** A regra 4 do `apply_kp_convention` (conserto do
  lote 40) auto-preenche `density_gbit` a partir de um `capacity` "pelado" em família DDR-kind:
  `capacity='2G'` → `density_gbit=''` vira `'2Gb'`. É fill-only e correto — só saiba que o gravado
  difere do arquivo, para não abrir falso alarme de "alguém mexeu no meu known_part".
- **`density_gb` existe e é diferente de `density_gbit`** (não mencionado na tabela do §1): `density_gbit`
  é o die em **bit** (`"4Gb"`) e **não** entra no bloqueio de medida; `density_gb` é o mesmo die em
  **byte** (`"512MB"`) e **entra**. E densidade sub-1Gb precisa ser FRAÇÃO (`"0.5Gb"`, nunca
  `"512Mb"`): o `_GBIT_RE` só casa o sufixo literal `Gb`, então `"512Mb"` vira densidade
  invisível em silêncio.

---

## 5. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no `ProfitabilityConfig`
(admin, o dono edita). ⚠ **É dado mutável** — muda com o mercado — por isso este doc **não cita valores
nem veredictos por família**.

Regras duráveis (essas não mudam): nunca reimplementar a regra de rentabilidade em outro lugar; se for
memória, `capacity` sempre em MB/GB, nunca Gbit (senão vira INDETERMINADO = bloqueador).

⚠️ **Nota de 2026-09-01 (após a pesquisa do `MEMA032G`) — o bloco abaixo é a análise de contingência da
Hipótese A, e a evidência reunida em §3.1 aponta fortemente pra Hipótese B (memória) para esta marca.**
Mantido por registro e por precaução — não custou nada em código, é só texto — mas hoje a leitura mais
provável é que a ISOCOM entra pelo caminho comum de qualquer marca de memória (DDR/eMMC/etc., os
`chip_type`s que já existem), **não** pelo caminho de tipo novo/K9/`PLANO_SOC.md` descrito abaixo. Isso
só muda se um PN futuro do cluster ISOCOM apontar de volta pra optoeletrônica — por isso o bloco não foi
apagado.

**Achado específico da ISOCOM (verificado em código, `chips/chip_types.py`, 2026-09-01) — ao contrário
da ISSI:** a ISSI encontrou cobertura pronta (`SRAM`/`NOR Flash`/`NAND Flash` já existiam no
vocabulário). A ISOCOM **não tem essa sorte se a Hipótese A (§3.1) se confirmar**:
- Não existe `chip_type` para optoacoplador, fototransistor, LED ou semicondutor discreto no
  vocabulário atual — nem mesmo na categoria genérica `catalog` (que hoje cobre NOR Flash, OneNAND, MCP,
  ePoP, SoC, PMIC, Sensor, SRAM, Mask ROM, NVMe SSD, BGA SSD — nenhum é a mesma coisa).
- Se confirmado, o primeiro passo real de gramática desta marca **provavelmente é abrir um `chip_type`
  novo** (nome, `category`, `label_kind`, `profit_family`, `commercial` — ver `ChipTypeSpec` em
  `chips/chip_types.py`) — o que **dispara o Handshake de rentabilidade** (`RentabilidadeHandshakeTests`)
  descrito em `AUTORIA.md §3.4`: nenhum tipo comercial pode ficar em INDETERMINADO com specs saudáveis.
  **A decisão de qual é a regra de rentabilidade (sempre rentável? nunca? depende de spec como CTR?) é
  do dono — eu preparo a proposta com o que a pesquisa Tier-1 trouxer, nunca decido o limiar sozinho.**

  ⚠️ **CORREÇÃO 2026-09-01 (auditoria do dono) — abrir um `chip_type` novo tem TRÊS consequências, e
  este `.md` só cobria uma.** Antes de propor qualquer tipo, saiba que as outras duas existem, porque
  elas mudam a proposta inteira:

  1. **RENTABILIDADE** — o handshake, já descrito acima. ✅ coberto.
  2. **PREÇO — o tipo nasce SEM chave de preço, e isso é estrutural.** `pricing/engine.py::
     `derive_price_key` abre com `if kind not in KINDS`. Medido em 2026-09-01:
     ```
     KINDS com chave de preço: ddr · emcp · emmc · k9 · lpddr · ssd · ufs · umcp
     SoC       → SEM CHAVE: tipo 'SoC' fora do mercado de preço (triagem descarta)
     NOR Flash → SEM CHAVE: tipo 'NOR Flash' fora do mercado de preço (triagem descarta)
     SRAM      → SEM CHAVE: tipo 'SRAM' fora do mercado de preço (triagem descarta)
     ```
     Todo tipo de categoria `catalog` (`label_kind='none'`) cai fora do preço **por construção**. Dar
     preço a um tipo novo exige mexer em `pricing/models.py` (`KIND_CHOICES` + `KIND_UNIT`) — que é
     código de precificação, fora do escopo deste chat (regra de ouro #14).
  3. **CAIXA FÍSICA** — `label_kind='none'` faz o `_compute_destination` cair no ramo desconhecido:
     a etiqueta vira o **nome cru do `chip_type`** e a categoria vira `'unknown'` (medido; ver a
     correção no §1). E o código de caixa F12 é **eterno** — nunca reordena nem se reusa.

  ⚠️ **E existe um precedente que este `.md` não conhecia: o `K9`.** Se a Hipótese A se confirmar, o
  molde a seguir NÃO é DDR/eMMC (tier por capacidade) — é o **K9**, que o dono criou em 2026-08-14
  justamente para um **tipo PLANO**: sem marca, sem capacidade, sem geração. A chave dele é FIXA
  `('k9', '', 1, '')` — "1 unidade" é o tier inteiro da categoria — e o ¥ mora no `Buyer`
  (`k9_rmb_each`), sem grid de preço. Note que `KIND_UNIT` **nem tem entrada** para `k9`: a unidade é
  vazia, porque não há o que medir.

  Um optoacoplador é exatamente esse formato: preço por peça, sem GB nem Gb (as únicas unidades que o
  `UNIT_CHOICES` conhece hoje). **Então a proposta ao dono, se a Hipótese A confirmar, é: "tipo novo
  no molde do K9" — não "tipo novo com tier de capacidade", que não teria como existir.** Ler o
  branch `_k9_quote` e o `derive_price_key` antes de propor.

  **Antes de propor, ler `PLANO_SOC.md` inteiro.** Existe um estudo do dono já pronto (2026-08-17,
  status ESTUDO — nenhuma linha de código alterada, aguardando decisão dele) que percorreu esse EXATO
  caminho pra outro tipo `catalog` (`SoC`): "o sistema já tem o molde pronto — o K9 é exatamente
  isto". Ele mapeia os 11 pontos de toque do K9 (`chips/chip_types.py`, `chips/engine.py`,
  `estoque/views.py`, `pricing/models.py`, `pricing/engine.py`, `pricing/views.py`) com arquivo:linha
  exato — MAIS dois achados que nem este `.md` nem a auditoria de 2026-09-01 cobriram: (1) a
  categoria `catalog` NÃO pode sair do tipo mesmo virando `commercial=True` — sequestra o `subtype`,
  provado empiricamente no plano — então o padrão certo é `commercial=True` MANTENDO
  `category="catalog"`, igual o K9 fez com `nand_raw`; (2) a tela do comprador (`pricing/views.py`,
  `partner_kind.html`) rejeita hoje um `tier_unit=''` fora de `('GB','Gb')` — o mesmo obstáculo que um
  tipo no molde K9 bateria ali, já diagnosticado no plano (§7) mas não resolvido. O plano é sobre
  SoC/Spreadtrum, não ISOCOM — mas o padrão arquitetural é idêntico ao que a Hipótese A exigiria:
  adaptar um caminho já mapeado, não redesenhar do zero.
- Se a Hipótese B se confirmar (é memória), os tipos DRAM/gerenciados padrão já cobrem, igual a toda
  outra marca — nada novo a declarar a priori.

*Nota de contexto (não é rentabilidade, é onde a marca cairia na UI de preço hoje):* ao contrário da
ISSI (já citada em `PROMPT_PRECOS.md` como "marca sem aba própria"), a ISOCOM **não aparece em nenhum
lugar** desse documento (conferido nesta sessão) — hoje ela simplesmente não tem chave de preço nenhuma,
nem via `Other Brands` nem via o curinga Nanya. Isso é esperado para uma marca 100% nova e não é urgente
resolver antes da gramática/known_parts existirem.

---

## 6. Gaps e Roadmap

- [x] **Confirmar O QUE a ISOCOM fabrica** (§3.1) — **resolvido com alta confiança em 2026-09-01.**
  "ISOCOM" pra memória é marca da Shenzhen Longsys Electronics (dona de Foresee/Lexar), confirmado via
  disputa de marca real na USPTO (TTAB 91256263) contra a Isocom Components (optoeletrônica) — as duas
  são empresas diferentes brigando pelo mesmo nome, e a Longsys perdeu o registro americano mas parece
  ter seguido fabricando/exportando sob o nome fora dos EUA. Chip_type = eMMC (vocabulário já existe,
  NENHUM chip_type novo necessário — a análise de contingência do §5 pra Hipótese A fica só histórico).
- [x] **Primeira submissão de known_parts criada** — `submissions/isocom_mema_2026-09-01.yaml`:
  `MEMA032G` (32GB) e `MEMA064G` (64GB), `chip_type: eMMC`, `confidence: manual` (fonte de capacidade
  é anúncio de marketplace único por PN, não datasheet nem distribuidor estruturado — ver rationale no
  cabeçalho do arquivo). Falta o dono rodar os comandos (ver §8 última entrada ou o arquivo em si).
- [x] **`MEMA016G` resolvido — 2026-09-01, com known_part de verdade (não só gramática).** Gatilho:
  PN ao vivo do debug de estoque do dono (`in_review_queue=true`, fuzzy-match já apontava `MEMA032G,
  MEMA064G`). Primeira tentativa foi cobrir só via gramática (capacidade derivada da regra
  posicional, sem fonte própria) — uma 2ª busca mais funda achou a lista de fornecedores aprovados
  de eMMC da Rockchip, que confirma 16GB de forma independente. `MEMA016G` ganhou known_part próprio
  (`confidence: distributor`) em `submissions/isocom_mema_r2_2026-09-01.yaml`; a gramática (`MEMA`,
  `isocom.yaml`) segue cobrindo qualquer sibling futuro sem fonte própria. Ver §3.2.
- [ ] **Subir a confiança de `manual` pra `confirmed`** nos 2 known_parts já submetidos — precisa de
  datasheet real da Longsys (não encontrado ainda), teste físico do chip pelo dono (programador/
  adaptador eMMC), ou uma 2ª fonte estruturada (LCSC/DigiKey/Octopart) confirmando os mesmos números.
- [x] **Versão JEDEC exata do eMMC — CONFIRMADA 5.1** (2026-09-01, lista Rockchip). Já preenchida
  como `interface: 'eMMC 5.1'` nas famílias `MEMA`/`MEMD` (`isocom.yaml`). Os 2 known_parts mais
  antigos (`MEMA032G`/`MEMA064G`, `isocom_mema_2026-09-01.yaml`) ainda estão com `interface` vazio —
  ficam como estavam (arquivo já pode estar em revisão do dono); os 3 known_parts novos
  (`isocom_mema_r2_2026-09-01.yaml`) já saem com `interface: 'eMMC 5.1'` preenchido.
- [ ] **Confirmar o domínio/site oficial da Longsys pra linha ISOCOM especificamente** — sabemos que
  `longsys.com` é o site da empresa-mãe (confirmado, tem páginas `/brand/foresee/` e `/brand/lexar/`),
  mas não achei uma página `/brand/isocom/` equivalente nem datasheet da linha ISOCOM lá.
- [x] **`chips/knowledge/isocom.yaml` criado** (2026-09-01) — bloco `brand` apenas, seguindo o
  precedente `winbond.yaml`, só pra destravar `submit_known_parts` em dry-run (§0.2 regra 3). `code:
  "ISC"` é palpite deste chat — **pendente confirmação do dono antes do primeiro `--commit`** (agora
  que a empresa real é conhecida, "LSY" ou similar também seria defensável — decisão do dono).
- [x] **Primeira família (Trilha A/gramática) criada — 2026-09-01, acabou virando DUAS.** `MEMA`
  (capacidade em `pn[4:7]`) e `MEMD` (estrutura idêntica à FEMD da Foresee, capacidade em `pn[6:9]`
  após grade `NN`), ambas eMMC 5.1, mapa `ISC_EMMC_CAP` compartilhado (`016`/`032`/`064`) em
  `chips/knowledge/isocom.yaml`. Gatilho: PN ao vivo `MEMA016G` (item acima) — a condição que esta
  entrada pedia ("assim que houver PNs suficientes") se cumpriu com um PN real, não com generalização
  especulativa; `MEMD` apareceu de bônus na mesma fonte que resolveu o `MEMA016G` (lista Rockchip).
  Detalhamento completo em §3.2.
- [ ] **Golden `_ISOCOM_GOLDEN` + `IsocomLoadBrandsTests`** — rascunho PRONTO com 5 âncoras (3×
  `MEMA` + 2× `MEMD`, ver bloco no fim desta seção), **não colado em `chips/tests.py`** (fora do meu
  escopo editar `.py` sem pedir — §0.2). Veredito de rentabilidade (`RENTÁVEL` pros 5) preenchido com
  confiança — `ProfitabilityConfig.emmc_min_cap_gb` nasce do field default (4.0 GB) em qualquer banco
  de teste limpo (`TestCase`, confirmado via migration `0010_profitabilityconfig.py` sem seed) —
  **mas sinalizado no rascunho** que esse mesmo mecanismo já divergiu sandbox×produção antes neste
  projeto (K3QF/LPDDR3), então vale o dono confirmar rodando a suíte de verdade. Falta o dono (1)
  colar o bloco em `chips/tests.py`, (2) rodar `load_brands --brand isocom` dry-run (aqui só validei
  o schema Pydantic manualmente, sem Django disponível neste ambiente) antes do `--commit`, e (3)
  rodar `submit_known_parts` pros dois arquivos de submissão (`isocom_mema_2026-09-01.yaml` +
  `isocom_mema_r2_2026-09-01.yaml`).
- [ ] **Se a Hipótese A voltar a ficar relevante** (hoje considerado muito improvável após o achado
  Longsys/TTAB): propor ao dono `chip_type` novo + Handshake de rentabilidade — ver `PLANO_SOC.md`
  (molde K9→catalog) antes de rascunhar. Mantido só por precaução histórica.

### Rascunho de golden (para `chips/tests.py` — NÃO colado no arquivo real, eu não edito `.py`)

Inserir depois de `class ESMTLoadBrandsTests` (bloco atual termina por volta da linha ~2360),
imediatamente antes de `class KnownPartsLoadTests` — mesma posição relativa que cada marca nova vem
ocupando (dict `_<MARCA>_GOLDEN` + classe `<Marca>LoadBrandsTests` colados juntos, "uma entrega só"):

```python
_ISOCOM_GOLDEN = {  # ISOCOM (provavelmente Shenzhen Longsys Electronics, ver §3.1) — 1a entrega
                     # (onboarding 2026-09-01): familias MEMA e MEMD (eMMC). Capacidade LITERAL
                     # no PN, mesma tabela ISC_EMMC_CAP em posicoes diferentes por familia.
                     # MEMA016G/032G confirmados via lista Rockchip (dl.radxa.com); MEMA064G via
                     # Alibaba; MEMDNN032G-M1S07/MEMDNN064G-M1D03 via lista Rockchip (familia
                     # irma, estrutura identica ao FEMD da Foresee). Ver ISOCOM.md §3.2.
    "MEMA016G": ("eMMC", "16GB", "", "", "", "RENTÁVEL"),
    "MEMA032G": ("eMMC", "32GB", "", "", "", "RENTÁVEL"),
    "MEMA064G": ("eMMC", "64GB", "", "", "", "RENTÁVEL"),
    "MEMDNN032G-M1S07": ("eMMC", "32GB", "", "", "", "RENTÁVEL"),
    "MEMDNN064G-M1D03": ("eMMC", "64GB", "", "", "", "RENTÁVEL"),
}


class IsocomLoadBrandsTests(TestCase):
    def test_carrega_o_yaml_fielmente(self):
        _carrega_marca_e_confere_fidelidade(self, "isocom")

    def test_identifica_todos_os_pns(self):
        from django.core.management import call_command
        from chips.engine import clear_engine_cache
        call_command("load_brands", "--brand", "isocom", "--commit", "--skip-known-parts", verbosity=0)
        clear_engine_cache()  # lru_cache por versão colide entre testes (DB reinicia)
        for pn, esperado in _ISOCOM_GOLDEN.items():
            self.assertEqual(_ident(pn), esperado, f"identificação mudou p/ {pn}")
```

Por que o veredito `RENTÁVEL` já vem preenchido (diferente do rascunho do `_ESMT_GOLDEN` em
`ESMT.md §6`, que deixou `<A CONFIRMAR>` pro DDR3L/DDR3): o branch eMMC de `assess_profitability`
(`chips/engine.py`) compara contra `ProfitabilityConfig.emmc_min_cap_gb` — essa config É lida do
banco, mas é um singleton criado via `get_or_create(pk=1)` (`chips/models.py::get_config`) SEM
`defaults` custom, e a migration que cria o campo (`0010_profitabilityconfig.py`) não tem
`RunPython`/seed — só o field default (`4.0`). Como o golden roda em `TestCase` (banco de teste
limpo a cada run, nunca uma cópia do banco de produção), o valor visto pelo teste É o default —
16/32/64GB folgam acima de 4GB **independente** de qualquer config que o dono tenha feito no admin
de produção (essa só afeta o app rodando de verdade, nunca o banco de teste transacional do
`TestCase`). Ainda assim vale o dono rodar a suíte de verdade pra confirmar — não há Django
disponível neste ambiente pra rodar de fato, e **este mesmo mecanismo (`ProfitabilityConfig` como
singleton editável) já divergiu sandbox×produção antes neste projeto** (K3QF/LPDDR3, ver memória
`wtc-k3qf-profitable-threshold-nao-respeita-tip`) — lá a divergência era ENTRE dois ambientes de
app rodando de verdade (não o `TestCase`, que é isolado por transação e não herda config de
produção), mas é motivo suficiente pra não tratar este veredito como 100% blindado sem o dono
efetivamente rodar a suíte uma vez.

---

## 7. Fontes de pesquisa

Ver §0.3 (hierarquia completa, ainda sem nenhum precedente ISOCOM testado). Ponto de partida: confirmar
primeiro a identidade (§3.1) — só então buscar site oficial + datasheets, Octopart, Alldatasheet, LCSC,
DigiKey/Mouser sob o nome certo. Evitar como fonte de capacidade/spec principal: qualquer distribuidor
sem rastreio e resumo de IA sem verificação — mesmo cuidado que todas as outras marcas do WTC.

---

## 8. Histórico (o *porquê* — durável)

- **2026-09-02 (6a rodada) -- `MEMDNN064G` (forma bare) aparece ao vivo no estoque, engine ja
  classifica certo sozinho; `pn_length` da MEMD resolvido por evidencia de campo; known_part bare
  criado apos o dono corrigir minha 1a decisao. Tambem: 5 rodadas de verificacao de uma "pesquisa" de
  IA de terceiro trazida pelo dono pro PN `MDXC2024G-M4`, todas as citacoes caindo ao fetch direto.**
  Debug de estoque mostrou `MEMDNN064G` (10 chars, sem sufixo), `in_review_queue=false` -- a gramatica
  MEMD (criada na 5a rodada) ja classificou certo sozinha: eMMC 64GB, ISOCOM, eMMC 5.1, RENTAVEL, via
  `fuzzy_suggestions: MEMDNN064G-M1D03`. Nao precisava de acao nenhuma pra classificacao, mas essa e a
  PRIMEIRA vez que se ve a forma sem sufixo desta familia na pratica -- resolvi a lacuna que a MEMD
  tinha desde que foi criada (nao se sabia se o chip fisico seria marcado com ou sem sufixo) e
  atualizei `pn_length` de `null` pra `10` (mesmo papel do `pn_length=8` da MEMA). Decidi inicialmente
  NAO criar known_part novo (so o scan, sem fonte citavel pra string bare especifica) -- o dono
  corrigiu, apontando o precedente ja usado na propria MEMA016G (capacidade herdada de uma entrada COM
  sufixo da mesma lista Rockchip, registrada bare uma vez que a convencao fisica da familia ja estava
  confirmada). Criado `submissions/isocom_memd_2026-09-02.yaml`: `MEMDNN064G` 64GB eMMC 5.1,
  `confidence: distributor`, mesma fonte Rockchip do irmao `MEMDNN064G-M1D03`. Ver secao 3.2
  (atualizacao) e `isocom.yaml` (reasoning da MEMD).

  Em paralelo (mesmo periodo, PN `MDXC2024GM4`/`MDXC2024G-M4`, sem relacao com o MEMDNN064G):
  pesquisa propria exaustiva (13+ buscas) nao achou fonte nenhuma; o dono trouxe entao uma "pesquisa"
  de outra IA/ferramenta, em 3 rodadas sucessivas, cada uma com citacoes novas pra sustentar
  fabricante e capacidade (24Gb LPDDR4). **Verifiquei TODAS via fetch direto -- nenhuma resistiu:** 1
  citacao confirmada falsa duas vezes (eet-china.com, real mas nao menciona o PN), 1 provavel URL
  inventada por extrapolacao (reverse-costing.com), 1 dominio real mas de assunto totalmente
  diferente (rf-china.com, e site de componentes de RF/radio, nao memoria), e 1 citacao real que
  achou "24Gb" numa linha de OUTRO fabricante (cseker.com, numero de um PN da BIWIN). A UNICA
  citacao genuinamente real (dzsc.com) confirmou o PN e o pacote BGA mas, mesmo perguntada
  diretamente, nao tem NENHUMA informacao de capacidade. O dono confirmou fisicamente "ISOCOM" e o
  numero de lote (`193419081168`) impressos no chip -- aceito a marca por confirmacao fisica (mesmo
  padrao da MEMA032G), mas capacidade/tipo seguem sem fonte real; nenhum known_part criado. Licao
  registrada em `wtc-verificar-citacoes-resposta-ia-terceiros.md`: citacao de dominio real nao
  garante que a alegacao especifica seja verdadeira -- cada URL tem que ser aberta e conferida.
- **2026-09-01 (mesmo dia, 5ª rodada) — gatilho `MEMA016G` ao vivo do estoque do dono: 1ª família
  (Trilha A/gramática) da marca criada; buscando fonte pra ele achei uma família-irmã inteira
  (`MEMD`) de brinde.** O dono colou o debug de estoque de um PN escaneado de verdade: `MEMA016G`,
  `in_review_queue=true`, 100% desconhecido, mas o próprio fuzzy-match do engine já apontava
  `MEMA032G, MEMA064G` — os dois known_parts confirmados 2 rodadas atrás. Em vez de tratar como um 3º
  known_part isolado (a mesma disciplina fraca que a rodada anterior já tinha corrigido), fui atrás
  de uma fonte de verdade pra ele antes de recorrer só à gramática — e achei uma **lista de
  fornecedores aprovados de eMMC da Rockchip** (`RKeMMCSupportList`, `dl.radxa.com`, doc técnico de
  fabricante de SoC pra qualificação de hardware): confirma `MEMA016G-M0T00` (16GB) e `MEMA032G-M0D01`
  (32GB), **e revela a versão eMMC exata (5.1)** que faltava pros dois. Na MESMA tabela, lado a lado,
  apareceu um prefixo que eu não conhecia: `MEMDNN032G-M1S07` (32GB) e `MEMDNN064G-M1D03` (64GB) —
  estrutura idêntica à FEMD da Foresee (grade NN + capacidade + G), specs idênticas às MEMA032G/064G
  já conhecidas. Não ignorei — criei a 2ª família (`MEMD`) junto, mesma entrega. Montei a gramática:
  famílias `MEMA` e `MEMD` (eMMC) em `chips/knowledge/isocom.yaml`, capacidade posicional literal
  (mapa `ISC_EMMC_CAP` compartilhado, posição diferente por família), reaproveitando a MESMA
  convenção da Foresee — reforça ainda mais a hipótese Longsys da rodada anterior. Isso reverte uma
  entrada do roadmap (§6) que dizia "2 known_parts não é suficiente pra generalizar com segurança" —
  não é sobre os mesmos 2 dados de antes, é sobre um PN real ter aparecido precisando de resolução
  AGORA (a condição que aquela entrada já previa: "assim que houver PNs suficientes"). Criei
  `submissions/isocom_mema_r2_2026-09-01.yaml` com 3 novos known_parts (`MEMA016G`,
  `MEMDNN032G-M1S07`, `MEMDNN064G-M1D03`), `confidence: distributor` (fonte técnica única — lista
  Rockchip — ainda não cruzada com uma 2ª fonte independente, mais forte que marketplace mas abaixo
  da barra de 3 fontes pra `confirmed`); o arquivo original (`isocom_mema_2026-09-01.yaml`, `confidence:
  manual`) fica intocado. Preparei também o rascunho do `_ISOCOM_GOLDEN` + `IsocomLoadBrandsTests`
  (não colado em `chips/tests.py` — fora do meu escopo editar `.py` sem pedir), com 5 âncoras e
  veredito de rentabilidade JÁ preenchido (`RENTÁVEL` pros 5) depois de confirmar que
  `ProfitabilityConfig.emmc_min_cap_gb` nasce do field default (4.0) em qualquer banco de teste limpo
  (migration `0010_profitabilityconfig.py` não tem seed custom) — mas sinalizado explicitamente que
  esse MESMO mecanismo já divergiu sandbox×produção antes neste projeto (K3QF/LPDDR3), então vale o
  dono confirmar rodando a suíte de verdade. Ver §3.2 (estrutura do PN, MEMA e MEMD) e §6 (roadmap +
  rascunho de golden atualizados) pro detalhamento completo. A relação exata entre MEMA0xxG e
  MEMDNNxxxG-xxxxx (mesmo produto, dois nomes? Ou dois SKUs?) fica em aberto, documentada como
  observação, não fato — não afeta a classificação de nenhum dos dois.
- **2026-09-01 (mesmo dia, 4ª rodada) — feedback do dono: pesquisar o cluster de PNs com mais
  exaustão; 2ª busca confirmou que não havia mais nada além dos 3 já conhecidos.** Depois da
  confirmação física do MEMA032G (fotos) e do pedido pra fechar a pesquisa (rodada anterior), o dono
  deu um feedback direto: "SEMPRE procure o máximo possível de PNs (...) com certeza no caminho você
  viu muito mais". Levei a sério e refiz a busca: páginas de marca/categoria de distribuidor,
  extremos de capacidade (`004`/`008`/`128`/`256`), e um lead que parecia expandir o cluster — um
  anúncio Alibaba "Phison EMMC MEMA Series 32GB 64GB 128GB 256GB". Investiguei até o fim e descartei:
  a linha real da Phison se chama **MEM5** (confirmado por outro anúncio, "Phison Emmc Mem5 Serie
  4gb 8gb 16gb"), então o "MEMA" daquele título é erro/confusão do vendedor, não um 4º fabricante
  genuíno da família — **não é evidência de PNs ISOCOM adicionais, não re-investigar essa pista**.
  Resultado honesto da 2ª busca: nada além dos 3 PNs já conhecidos (016/032/064). Lição registrada na
  memória do projeto (`wtc-maximizar-pns-por-rodada-tier1.md`) pra valer em TODAS as marcas, não só
  ISOCOM.
- **2026-09-01 (mesmo dia, 3ª rodada) — identidade da empresa real encontrada: Shenzhen Longsys
  Electronics, disputa de marca com a Isocom Components confirmada via TTAB, e submissão criada.**
  O dono trouxe 2 fontes novas (digipart.com/part/MEMA032G + anúncio Alibaba "MEMA032G-Longbo-32GB-
  ISOCOM-eMMC-flash") pedindo pra fechar a pesquisa. Investigando mais a fundo achei: pedido de marca
  USPTO da Longsys pra "ISOCOM" (serial 88496930, 2019, classe 009, explicitamente pra chips/circuitos
  integrados/memória) e o caso TTAB nº 91256263 "Isocom Components 2004 Limited v. Shenzhen Longsys
  Electronics Co., Ltd." — oposição da Isocom Components MANTIDA, pedido da Longsys ABANDONADO em
  26/10/2020 (trademarkelite.com). A Longsys é a MESMA dona da Foresee e da Lexar (já onboardadas/
  conhecidas neste projeto) — resolve o mistério inteiro: duas empresas reais brigando pelo mesmo
  nome, a Isocom Components venceu nos EUA (por isso o catálogo dela não tem "MEMA"), a Longsys
  parece ter seguido fabricando/exportando sob "ISOCOM" fora do registro americano. RS Components
  (distribuidor estruturado) só lista os optoacopladores genuínos sob "Isocom" — zero memória lá,
  reforçando a separação. Achei também o título do anúncio Alibaba do MEMA064G
  ("MEMA064G-M0S00-EMMC-64GB-153FBGA-Memory") — mesma marcação "M0S00" do chip físico do dono,
  confirma 64GB + eMMC + 153-Pin FBGA. MEMA016G existe (ariat-tech.com) mas sem capacidade
  confirmada em nenhuma fonte — excluído. **Criei `submissions/isocom_mema_2026-09-01.yaml`** com
  MEMA032G (32GB) e MEMA064G (64GB), `confidence: manual` (fonte de capacidade é anúncio de
  marketplace único por PN — corpo das páginas Alibaba não renderizou via fetch automatizado, só os
  títulos — mais forte que nada, mais fraco que o padrão de 3 fontes cruzadas deste projeto pra
  `confirmed`). Atualizei `ISOCOM.md` §3.1/§6 com o relato completo.
- **2026-09-01 — Pesquisa Tier-1 do primeiro PN real, `MEMA032G` (pedido do dono), e criação do
  `chips/knowledge/isocom.yaml`.** Pesquisa em Tier-1 pra tentar decidir a Hipótese A vs. B do §3.1: o
  catálogo oficial da Isocom Components (PDF, 60 págs., lido na íntegra) e o site oficial `isocom.com`
  **não citam "MEMA" em lugar nenhum** — Hipótese A (optoeletrônica) contradita para este PN. Fontes de
  distribuidor acessíveis (`oemstrade.com`, `sili-tech.us`, `digipart.com`, nível Tier-3) mostram o
  padrão de família `MEMA016G`/`MEMA032G`/`MEMA064G` (progressão 16/32/64). Várias fontes relevantes
  bloquearam com Cloudflare/403 (`ic-components.com`, `ariat-tech.com`, `allelcoelec.com` pra este PN,
  a página de teardown `reverse-costing.com`, dois PDFs `fcc.report`) — não contornado, conforme a
  política de fetch do WTC. Um match de "MEMA" que o `WebFetch` alegou contra `MX52LM08A11XV` foi
  identificado como extração incorreta (a substring não existe de fato) e descartado como evidência.
  **Duas confirmações físicas do dono, via `AskUserQuestion`:** o chip é pacote **BGA**, e **"ISOCOM" e
  "MEMA032G" aparecem os dois impressos nele.** Conclusão: Hipótese B favorecida com alta confiança
  (memória, provavelmente eMMC dado BGA + contexto de reciclagem de tablets/TV boxes) — mas capacidade
  exata, protocolo exato e o fabricante real seguem **não confirmados**, então **nenhum known_part foi
  submetido** (regra de ouro #13: spec essencial não confirmável em Tier-1 → excluir, nunca estimar).
  Criado `chips/knowledge/isocom.yaml` (bloco `brand` apenas, seguindo o precedente `winbond.yaml`) só
  pra destravar `submit_known_parts` em dry-run (§0.2 regra 3); `code: "ISC"` é palpite deste chat,
  pendente confirmação do dono. Ver §3.1 (relato completo), §5 (nota sobre a análise de contingência da
  Hipótese A) e §6 (roadmap atualizado) pros detalhes.
- **2026-09-01 — Auditoria do dono (revisão cruzada por outro chat).** Cada afirmação técnica foi
  conferida rodando o código, não lendo. **Confirmadas corretas:** os 11 tipos de categoria `catalog` e
  o fato de todos serem `commercial=False`; a ausência TOTAL de qualquer tipo para optoacoplador/LED/
  discreto (`grep` por opto|led|diodo|transistor|coupler em `chip_types.py` → **zero**); o alias
  `isocell` no tipo `Sensor` e o alerta de não confundir com "Isocom"; e que o `submit_known_parts`
  exige a `Brand` já no dry-run. **O julgamento central do documento — recusar montar arcabouço de
  memória antes de saber o que a marca fabrica — foi considerado correto e mantido.**
  **Quatro lacunas fechadas:** (1) abrir um `chip_type` novo tem **TRÊS** consequências (rentabilidade,
  **preço** e **caixa**) e o `.md` só cobria a primeira — e existe um precedente que ele não conhecia,
  o **K9**, que é o molde certo para tipo PLANO com preço por unidade (§5); (2) `commercial=False` não
  é lido por nenhum consumidor em produção — "catálogo não tem caixa" é falso na prática (§1);
  (3) a regra de ouro #13 é disciplina, **não** trava — o portão aceita `capacity` vazio (§0.2);
  (4) faltavam três armadilhas sistêmicas no §4: bit em `capacity` passa o portão, o `save()` reescreve
  `density_gbit`, e `density_gb` × `density_gbit` × sub-1Gb fracionário.

- **2026-09-01 — Verificação independente desta auditoria (nova sessão, mesma marca).** Rodei cada
  comando/grep que a auditoria sugeriu ("não acredite em mim") direto no código, sem depender do que
  o `.md` já dizia: `grep` opto/coupler/diodo/transistor em `chip_types.py` → zero; `is_commercial`/
  `COMMERCIAL_TYPES` só em `chip_types.py` + `tests_convention.py` → confirmado, zero em
  `estoque/views.py`/`pricing/`; `KnownPartSpec.capacity=""` sem trava no portão → confirmado;
  `KINDS` = exatamente `{ddr,emcp,emmc,k9,lpddr,ssd,ufs,umcp}`, `derive_price_key` abre com
  `if kind not in KINDS` e devolve a MESMA string de motivo citada na auditoria → confirmado byte a
  byte; `KIND_UNIT` de fato não tem entrada `k9` → confirmado; `BYTE_ONLY_FIELDS=("emcp_ram",
  "emcp_nand")` e `_GBIT_RE` casando só o sufixo literal `Gb` (`chips/engine.py:448`) → confirmado;
  regra 4 do `apply_kp_convention` (`chips/knowledge/convention.py`) fazendo exatamente o fill-only
  de `density_gbit` descrito → confirmado. **Zero discrepância encontrada — a auditoria bateu 100%
  com o código atual.** Achado adicional, não uma correção: `ChipTypeSpec.commercial` é um campo real
  (`bool = True`, default), e os 11 tipos `catalog` (incl. `SoC`/`NOR Flash`/`SRAM`) o zeram
  EXPLICITAMENTE (`commercial=False`) — o `K9` não tem esse kwarg, então `commercial=True` nele é só
  o default intocado, não uma exceção especial de código. E achei um recurso que a auditoria não
  citou: **`PLANO_SOC.md`** já é o "molde K9 aplicado a um tipo `catalog`" por escrito, em detalhe
  operacional — ver o novo parágrafo em §5 e o item em §6.
- **2026-09-01 — criação deste `.md`.** Pedido do dono: ler `CLAUDE.md` (inteiro) e, como referência de
  formato, `SK_HYNIX.md`, e gerar o guia de convenções/processo pra ISOCOM virar "chat de marca" antes
  de qualquer PN real ser pesquisado — mesmo pedido, quase nas mesmas palavras, da sessão que criou o
  `ISSI.md` em 2026-08-05. Além dos dois arquivos indicados, li também `AUTORIA.md` inteiro (exigido por
  `CLAUDE.md §5` como leitura obrigatória de qualquer chat de marca) e usei o `ISSI.md` como molde
  estrutural mais próximo — mesma situação exata (marca 100% nova, mesmo pedido do dono) — dobrando pra
  dentro deste doc as obrigações cross-marca já consolidadas em outras sessões (disciplina de pesquisa em
  cluster, aritmética Gb/GB visível, listar known_parts no chat, excluir-não-adivinhar, nunca `--user` no
  comando entregue, não mexer em código sem pedir, restringir escopo de sub-agentes, reler doc
  compartilhado antes de sobrescrever, e o princípio "o objetivo é o banco, não a gramática").
- **2026-09-01 — achado técnico (verificado direto no código, não só citado de outra sessão):** li
  `chips/management/commands/submit_known_parts.py` (o trecho do `handle()`) e confirmei que
  `Brand.objects.filter(name=brand_name).first()` roda **incondicionalmente** — dry-run ou `--commit` —
  antes de qualquer confronto com o banco; se a marca não existir, o comando levanta `CommandError`
  (com sugestão de nomes parecidos via `difflib`). Trilha A destrava Trilha B pra qualquer marca nova,
  ISOCOM inclusa — mesmo achado que a sessão ISSI já tinha documentado, aqui reconfirmado de primeira
  mão no código, não só citado.
- **2026-09-01 — achado de vocabulário (verificado em `chips/chip_types.py`, lido na íntegra):** o
  vocabulário de `chip_type` cobre DRAM (discreta/móvel/GPU/legada), memória gerenciada (eMMC/UFS/eMCP/
  uMCP/SSD/NAND) e uma dúzia de tipos "catálogo" (NOR Flash, OneNAND, MCP, ePoP, SoC, PMIC, Sensor,
  SRAM, Mask ROM, NVMe SSD, BGA SSD) — **nenhum cobre optoacoplador ou semicondutor discreto.** Ao
  contrário da ISSI (que encontrou `SRAM`/`NOR Flash`/`NAND Flash` prontos), a ISOCOM pode precisar de
  tipo novo + Handshake de rentabilidade já na primeira família, **se** a Hipótese A do §3.1 se
  confirmar — não decidido aqui, só sinalizado (ver §5/§6).
- **2026-09-01 — achado de contexto (verificado em `PROMPT_PRECOS.md`, lido na íntegra, e em
  `grep -il isocom *.md` na raiz do projeto):** ao contrário da ISSI (já citada em `PROMPT_PRECOS.md`
  como "marca sem aba própria"), a **ISOCOM não aparece em nenhum `.md` do projeto** — zero precedente
  mais literal do que qualquer marca onboardada até aqui.
- **2026-09-01 — a pergunta em aberto mais importante desta sessão:** diferente de toda marca anterior
  do WTC (todas memória/storage/SoC), existe uma incerteza genuína sobre se "ISOCOM" aqui é a Isocom
  Components conhecida no mercado de optoeletrônica/discretos, ou outra entidade — ver §3.1. Nada foi
  decidido; a próxima sessão resolve isso ANTES de tocar em qualquer prefixo.
- Nenhuma família, nenhum known_part confirmado existe ainda para esta marca.
  `chips/knowledge/isocom.yaml` **existe desde 2026-09-01** (bloco `brand` apenas — ver entrada de
  histórico acima —, necessário só pra destravar `submit_known_parts` em dry-run), mas segue sem
  nenhuma família ou known_part.

> O inventário de chaves/mapas vai morar no **`isocom.yaml`** (já existe o bloco `brand`; famílias
> quando a pesquisa do cluster `MEMA*` fechar — §6); os **known_parts** confirmados (com a proveniência
> Tier-1 nas `notes`) vão viver no **banco**, submetidos via `submit_known_parts`. Tudo que é
> cross-marca (comandos, convenção, rentabilidade, arquitetura) está no **`CLAUDE.md`** — o único `.md`
> mantido nesse papel, e é quem aponta pro `AUTORIA.md`.

---

> **Regra de trabalho:** eu crio/edito o `isocom.yaml` e preparo arquivos de submissão de known_parts; o
> dono roda `load_brands --brand isocom` (sempre dry-run antes do `--commit`) e o `submit_known_parts`
> (idem) e aprova no admin. **Ponto mais importante, mais até do que em qualquer marca anterior:** antes
> de qualquer prefixo, confirmar O QUE a ISOCOM fabrica (§3.1) — a arquitetura inteira depende dessa
> resposta. Depois disso: a ISOCOM começa do ZERO como toda marca nova — toda família PRECISA de golden
> test, todo known_part PRECISA de fonte Tier-1 citada na `notes`, e PN ambíguo ou tipo genuinamente novo
> NUNCA se decide sozinho — pergunto ao dono primeiro.
