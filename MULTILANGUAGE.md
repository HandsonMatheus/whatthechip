# MULTILANGUAGE.md — O WhatTheChip em 4 idiomas

> **Documento de FEATURE + CONTRATO DE AUTORIA.** A primeira metade (§1–§6)
> descreve o sistema multilíngue do ponto de vista do produto — é a peça que
> entra na documentação geral. O **§7 é o CONTRATO**: as regras que **todo
> chat/agente que criar tela, página, mensagem ou string** segue para nascer
> traduzido sem quebrar a convenção — leitura OBRIGATÓRIA antes de criar
> conteúdo novo. A bíblia técnica (arquitetura, rotina profunda, armadilhas)
> é o **`I18N.md`** — em conflito, o código vence, depois o I18N.md, depois
> este. Convenção de engenharia: `CLAUDE.md` §6 ("Convenção i18n").
>
> Status: **no ar** desde 2026-07-08 · suíte com portões automáticos.

---

## 1. O que é

O WhatTheChip fala **quatro idiomas** em toda a interface — do site público à
bancada de triagem e ao dashboard do comprador:

| Código | Idioma | Público-alvo |
|---|---|---|
| `pt-br` | Português (Brasil) | idioma-fonte e fallback universal |
| `es` | Español | operadores no Paraguai / América Latina |
| `en` | English | mercado internacional |
| `zh-hans` | 中文 (simplificado) | compradores e parceiros na China |

A arquitetura foi desenhada para escalar a **~10 idiomas** sem mexer em código:
idioma novo ≈ catálogos de tradução + arquivos de conteúdo (ver §8).

---

## 2. Como o sistema escolhe o idioma (a cadeia de decisão)

Quatro camadas, da mais forte para a mais fraca — a primeira que responder, vence:

```
1. PREFERÊNCIA DA CONTA   usuário logado com idioma salvo no perfil
                          (segue a conta em qualquer dispositivo)
2. ESCOLHA NO SELETOR     cookie do navegador, vale por 1 ano
                          (funciona também deslogado / na bancada)
3. REGIÃO / NAVEGADOR     o idioma do navegador do visitante (Accept-Language):
                          visitante da China vê 中文, do Paraguai vê Español
4. PORTUGUÊS              fallback final
```

Por que **navegador** e não GeoIP: é o padrão da web para língua, respeita a
configuração da pessoa (um chinês viajando no Paraguai continua vendo 中文),
não depende de serviço externo e não é enganado por VPN.

---

## 3. Onde se troca o idioma

| Superfície | Seletor |
|---|---|
| Site público (topo) | dropdown de idiomas no topnav (🌐) |
| Login | seletor compacto abaixo do formulário |
| Painel / bancada (`/painel/`, `/estoque/`) | seletor no header escuro, ao lado de "Site/Sair" |
| Dashboard do comprador (`/partner/`) | seletor no header, ao lado das notificações |

Comportamento: **qualquer usuário troca quando quiser**. Se estiver logado, a
escolha é **gravada na conta** (camada 1) — vale em qualquer máquina dali em
diante. Deslogado, vale para aquele navegador (cookie, 1 ano).

O **dono** também pode pré-definir o idioma de cada conta no Django admin —
na ficha do usuário há o bloco **"Idioma da plataforma"** (útil ao criar a
conta de um operador ou comprador estrangeiro, já que não há cadastro público).

---

## 4. O que é traduzido (mapa por superfície)

| Superfície | Cobertura |
|---|---|
| **Site público** (busca, card de decodificação, modal "Adicionar chip", rodapé) | ✅ 100% da UI |
| **Home (conteúdo)** | ✅ traduzida nos 4 idiomas (hero, dicas, estatísticas, cartão de resultado) |
| **Bancada / painel / lotes** (gateway de triagem, caixas, filas, toasts, modais) | ✅ 100% da UI |
| **Login** | ✅ |
| **Dashboard do comprador** (`/partner/`, preços, notificações, estados de cotação) | ✅ |
| **Ditado por voz** (mic) e mensagens de JavaScript | ✅ (catálogo JS por idioma) |
| **Páginas de documentação** (fabricantes, contato) | mecanismo pronto; conteúdo em fila — enquanto não traduzido, aparece em PT (nunca em branco) |
| **Django admin** | **fixo em pt-br** de propósito: é ferramenta interna da plataforma (só o dono); fixar dá consistência total sem custo de manutenção |

## 5. O que NUNCA é traduzido (por design)

**Dados não são língua.** Ficam idênticos em qualquer idioma:

- Part Numbers, códigos FBGA, specs (`LPDDR4X`, `x16`, `8Gb`, `16GB`);
- **etiquetas de caixa física** (`EMCP16+1`, `UFS128GB`) — são códigos operacionais;
- nomes de marca (Samsung, SK Hynix, Micron…), termos de mercado (`eMMC`,
  `uMCP`, `datasheet`, `US$`);
- **valores gravados no banco** (motivo de reprovação na auditoria, snapshot do
  estoque, planilha exportada) — o dado é gravado em pt-br canônico; a tradução
  acontece só na tela. Isso garante que o histórico não vira uma mistura de
  idiomas conforme quem operou;
- os **valores canônicos** que a lógica do sistema compara (`RENTÁVEL`,
  `banco de dados`) — o usuário vê o rótulo traduzido (`有利润`, `database`),
  o sistema decide pelo valor canônico. Regra de bolso do projeto:
  **lógica compara CHAVE · usuário vê RÓTULO · banco guarda CANÔNICO.**

---

## 6. Como a tradução se mantém (a rotina, resumida)

O sistema cresce todo dia; a tradução acompanha por uma rotina desenhada para
ser executada por um **modelo de IA simples sem poder errar** — preso entre
dois portões:

```
strings novas no código
   → extração automática (makemessages / scripts/i18n_extract.py)
   → tradutor preenche SÓ as entradas novas, sob contrato
     (placeholders/HTML/glossário intocáveis; dúvida → marca "fuzzy")
   → PORTÃO: python manage.py check_translations
     (barra: entrada vazia, fuzzy, placeholder quebrado, HTML perdido,
      termo protegido traduzido, catálogo não compilado)
   → suíte de testes (renderização nos 4 idiomas + regras de canônico)
   → revisão do dono no diff → commit/deploy
```

Além do portão de catálogos, dois testes-sentinela quebram a suíte se alguém
programar fora da convenção: choices de modelo exibidos sem tradução
(`I18nChoicesDeclarationTests`) e superfície nova sem seletor de idioma
(`SeletorDeIdiomaPresenteTests`). Detalhe completo do contrato: `I18N.md` §7.

**Conteúdo editorial** (home, futuras páginas): cada página tem um arquivo por
idioma no repositório (`_content/index.es.html`…) — editar a versão PT implica
atualizar as traduções na mesma leva; enquanto não atualizar, o visitante
estrangeiro vê o trecho antigo (nunca uma página quebrada).

---

## 7. ⭐ CONTRATO DE AUTORIA — para TODO chat que criar tela, página ou string

> **A regra de ouro do autor: toda string nasce marcada E traduzida na MESMA
> entrega.** "Traduzir depois" não existe — depois = nunca (foi exatamente o
> bug de 2026-07-08: home, crachá de papel e admin entregues "para depois").
> O custo marginal de nascer traduzido é de minutos; o custo da varredura
> retroativa é uma sessão inteira com risco de landmine. Os portões
> automáticos pegam o que foi marcado errado — **não pegam o que nunca foi
> marcado**. A marcação é responsabilidade de quem cria a string.

### 7.1 — "Vou criar X" → faça Y (nunca Z)

| Vou criar… | FAÇA | NUNCA |
|---|---|---|
| Texto em template (novo ou editado) | `{% load i18n %}` + `{% trans "…" %}` / `{% blocktrans trimmed %}` (variável → `%(x)s`) | texto PT cru; marcar DADOS (PN, specs, `LPDDR4`, `x16`, marca, `{{ destination }}`) |
| Mensagem de view p/ usuário | `gettext` (eager) | `gettext_lazy` dentro de `JsonResponse`/`json.dumps` (estoura); esquecer o import |
| Choices de modelo EXIBIDO (`get_FOO_display`) | rótulos com `gettext_lazy`; se for admin-only/rótulo-dado → declarar em `I18nChoicesDeclarationTests.DECLARADOS` com justificativa | traduzir o VALOR (é chave de lógica); deixar sem decisão (suíte fica vermelha) |
| String exibida que TAMBÉM é comparada | criar CHAVE estável + rótulo traduzido (padrão `chips/labels.py`) | `{% if x == "texto em PT" %}` — a landmine clássica (I18N.md §8.1) |
| String PERSISTIDA no banco (motivos, snapshots, labels de caixa, export) | gravar o CANÔNICO pt-br + comentário `⚠ CANÔNICO — NUNCA traduzir` | passar por gettext no write (histórico viraria mistura de idiomas) |
| String em JS | inline no template → `'{% trans "…" %}'`; em `static/*.js` → `gettext('…')` (domínio `djangojs`) | concatenar frase de pedaços quando a ordem muda entre línguas — use placeholder |
| Página de CMS nova | `_content/<slug>.html` (PT) **+ os 3 irmãos** `.es/.en/.zh-hans.html` **+** metadados na chave `'i18n'` do `import_content` | entregar só o PT sem avisar. Conteúdo grande demais p/ traduzir na entrega? Entregue o PT, **declare a página na fila do I18N.md §10** e avise o dono — o fallback segura |
| Editar conteúdo PT existente que JÁ tem traduções | atualizar os `<slug>.<código>.html` na MESMA sessão | deixar as traduções defasadas em silêncio |
| Shell/layout novo (header próprio) | incluir `{% include "partials/lang_select.html" with variant='shell' %}` (ou default em fundo claro) | esquecer o seletor (`SeletorDeIdiomaPresenteTests` quebra) |
| Emoji/símbolo junto do texto | fora do `{% trans %}` (`⚠ {% trans "…" %}`); em Python, pode ficar no msgid (padrão `_CONF_LABEL`) | — |

### 7.2 — O fluxo do autor (depois de criar as strings)

```bash
1. python scripts/i18n_extract.py            # (ou makemessages) — liste SEUS msgids novos
2. adicione es/en/zh-hans dos SEUS msgids nos .po (django e/ou djangojs)
     — contrato do tradutor I18N.md §7.1: placeholders/HTML/glossário intocáveis;
       termos consagrados dos catálogos existentes; DÚVIDA → "#, fuzzy" + avisar o dono
     — não domina o idioma? entregue tabela msgid → 3 traduções p/ o chat i18n
3. python scripts/i18n_compile.py            # (ou compilemessages) — .po → .mo
4. python manage.py check_translations       # ← verde OBRIGATÓRIO
5. python manage.py test chips estoque --settings=core.settings_test
6. entregue TUDO no mesmo commit/PR (código + .po + .mo + conteúdo traduzido)
```

### 7.3 — E se o chat IGNORAR o contrato? (a resposta não é confiança)

O contrato não depende de obediência — é **imposto por tripwires na suíte**,
que todo chat roda no próprio checklist e o dono roda antes de qualquer merge
(o backstop final). A pilha de imposição, da mais automática à humana:

| O chat… | Quem pega | Como |
|---|---|---|
| marcou a string mas NÃO traduziu | `check_translations` **regra 8** (completude) | extrai os msgids do CÓDIGO (descoberta dinâmica — cobre app novo) e exige cada um em TODO catálogo; erro aponta `arquivo:linha` |
| nem marcou (texto PT cru no template) | `check_translations` **regra 9** | detector por diacrítico fora de `{% trans %}`; exceção deliberada = `i18n-ok` na linha (documentada no código) |
| traduziu quebrando placeholder/HTML/glossário | regras 3–5 do portão | diff estrutural msgid×msgstr |
| criou choices exibido sem `_lazy` | `I18nChoicesDeclarationTests` | lazy OU declarado, senão vermelho |
| criou shell sem seletor de idioma | `SeletorDeIdiomaPresenteTests` | presença nas 4 superfícies |
| traduziu valor canônico/lógica | `test_valor_canonico_nunca_muda` + suíte | o engine tem que seguir falando pt-br |
| **escreveu PT sem nenhum acento** (raro) ou tradução **errada de sentido** | **revisão humana do diff** (dono) | o único buraco não-automatizável — por isso a revisão continua no fluxo |

E tudo isso roda dentro de `python manage.py test chips estoque
--settings=core.settings_test` — **suíte vermelha = entrega recusada**, a
mesma regra que já vale para golden/handshake/tenancy.

### 7.4 — Rastreabilidade e edição das traduções (escala longa)

- **Fonte única = os `.po` no git** (`locale/<idioma>/LC_MESSAGES/django.po` +
  `djangojs.po`) — formato-padrão da indústria (gettext): texto puro,
  diffável em PR, compatível com Poedit hoje e Weblate/tradutor humano amanhã,
  sem migração.
- **Cada entrada carrega `#: arquivo:linha`** (onde a string vive no código) —
  Poedit/Weblate mostram o contexto; regeneradas a cada extração.
- **Quem escreveu/quando** = `git blame`/histórico do `.po` (cada chat entrega
  suas entradas no próprio commit).
- **Editar uma tradução** = editar o `msgstr` (Poedit, editor, ou pedir ao chat
  i18n) → `scripts/i18n_compile.py` → `check_translations` revalida →
  commit. Nunca se edita o `msgid` (§7.5, proibição 6).
- **Conteúdo CMS** = arquivos `_content/<slug>.<código>.html` no git — mesmo
  trilho (diff, blame, PR).

### 7.5 — As seis proibições do autor

1. **Texto PT cru** em template/view novo (o portão não enxerga o não-marcado).
2. **Traduzir** valor canônico, chave de lógica, dado ou string persistida.
3. **Mexer em msgstr alheio** — você só ADICIONA os seus; consertar tradução
   existente é tarefa do chat i18n (dono do I18N.md).
4. **Inventar mecanismo** (i18n_patterns, URL por idioma, `if lang == 'es'` na
   lógica, GeoIP, lib nova) — a arquitetura está fechada no I18N.md §2;
   proposta de mudança → perguntar ao dono, não implementar.
5. **Afrouxar os portões** — `PROTECTED_TERMS`, `check_translations`,
   `I18nChoicesDeclarationTests.DECLARADOS` sem justificativa não se tocam
   para "fazer passar".
6. **Traduzir o msgid** — o pt-br é a chave; muda o texto-fonte = muda a chave
   = tradução órfã em todos os idiomas.

---

## 8. Como adicionar um idioma novo (visão de produto)

1. Ativar o idioma na configuração (1 linha em `settings.LANGUAGES`).
2. Gerar e traduzir os 2 catálogos (`django.po` + `djangojs.po`) pela rotina §6.
3. Traduzir os arquivos de conteúdo que importarem (no mínimo a home).
4. `check_translations` verde → commit → deploy.

Sem migração, sem mudança de template ou engine: os seletores, o modelo de
preferência e a detecção leem a lista de idiomas da configuração. Custo real ≈
o volume de texto a traduzir.

---

## 9. Limitações conhecidas / fila

- **Páginas de fabricante** (`fab-samsung`…, `fabricantes`, `contato`):
  conteúdo ainda em PT (fallback), traduzir sob demanda de mercado.
- **Fragmentos técnicos do decode** (ex.: `"por die"`, `"consultar datasheet"`
  dentro de strings compostas do engine): aparecem em PT em qualquer idioma até
  a tokenização do vocabulário do engine (planejada; ver `I18N.md` §5.1).
- **Histórico persistido** (motivos de reprovação já gravados, exportações):
  exibido no canônico pt-br; rótulo traduzido on-read é evolução futura.

---

## 10. Ponteiros técnicos (para quem for mexer)

- **`I18N.md`** — a bíblia: arquitetura, decisões (§2), cadeia (§3), rotina de
  tradução com IA (§7), CMS files-first (§9), armadilhas (§8).
- **`CLAUDE.md` §6** — a convenção "toda string nova nasce no lugar certo"
  (tabela onde-nasce → portão que pega).
- Código-chave: `core/settings.py` (idiomas/cookie), `tenancy/models.py::UserLanguage`
  + `tenancy/middleware.py::UserLanguageMiddleware` (preferência),
  `tenancy/views.py::set_language`, `chips/labels.py` (rótulos do engine),
  `templates/partials/lang_select.html` (seletor), `pages/views.py::_localized_content_path`
  (conteúdo por idioma), `chips/management/commands/check_translations.py` (portão),
  `locale/` (catálogos), `chips/tests_i18n.py` (a rede de testes, 28 testes).
