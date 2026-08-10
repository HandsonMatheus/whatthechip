# Bug no portão de i18n — `check_translations` acusa 921 falsos "FALTA no catálogo"

> Cole isto no chat de **i18n** do WhatTheChip. Antes de corrigir, releia `I18N.md` §6–§7 e
> `MULTILANGUAGE.md` §7 — este prompt descreve o bug + o fix proposto; você **valida e executa
> dentro do contrato**. É infra de i18n (`.py`) → edita local, ENTREGA ao dono publicar (regra de ouro #1).

## Sintoma
`python manage.py test chips estoque --settings=core.settings_test` falha SÓ em
`chips.tests_i18n.PortaoDeCatalogoTests.test_catalogos_publicaveis`:

```
CommandError: 921 problema(s) de tradução — o catálogo NÃO está publicável.
✗ en/django:      FALTA no catálogo «session key»    (marcada em venv/lib/python3.14/site-packages/django/contrib/sessions/base_session.py:28)
✗ zh-hans/django: FALTA no catálogo «Change password» (marcada em venv/lib/python3.14/site-packages/django/contrib/admin/...)
... (~921, TODAS de django/contrib/{admin,auth,sessions,contenttypes} + modeltranslation/tests)
```
**Nenhuma** das strings é do WhatTheChip — são todas internas do Django / django-modeltranslation.

## Causa raiz (confirmada)
`chips/i18n_source.py::_local_app_paths()` (linhas 48-56) tenta pular o site-packages assim:

```python
if base in p.parents:      # "o app está dentro do BASE_DIR?"
```

A premissa é *"app dentro do projeto = local; site-packages fica FORA do repo"*. **Mas o `venv/`
desta máquina mora DENTRO do repo** (`chipdocs/venv/`, python3.14). Então os apps embutidos do
Django (`admin`/`auth`/`sessions`/`contenttypes`) e o `modeltranslation` — que vivem em
`chipdocs/venv/lib/python3.14/site-packages/…` — **passam** no teste `base in p.parents`, entram
como "apps locais", têm os `.py` varridos por `python_files()`, e suas ~900 strings marcadas
(`gettext_lazy` nos `verbose_name` etc.) são exigidas em todo `.po` → 921 falsos "FALTA".

## Evidência pra confirmar sozinho (não confie de graça)
- Catálogos LIMPOS: `grep -c site-packages locale/*/LC_MESSAGES/django.po` → **0** em todos. A
  poluição **não** está no `.po` — vem da EXTRAÇÃO ao vivo (regra 8 de completude).
- Todas as "FALTA" apontam pra `venv/.../site-packages/`.
- `ls -d venv` na raiz confirma o venv dentro do BASE_DIR; `git check-ignore venv/` → ignorado.
- `_local_app_paths()` é chamado por `python_files()` **e** `template_files()` → é o ÚNICO ponto de
  vazamento (`js_files()` usa `static/js`; `core/` é adicionado à parte; nenhum toca o venv).

## Impacto
Falso alarme **LOCAL** apenas (venv-no-repo). **NÃO bloqueia produção**: o build do Render roda
`migrate`+`collectstatic`, não a suíte; e lá o venv não fica no BASE_DIR, então o portão passa.
MAS deixa a suíte local **vermelha pra sempre**, mascarando falhas reais → tem que consertar.

## Fix proposto (mínimo, 1 linha) em `_local_app_paths()`
```python
if base in p.parents and 'site-packages' not in p.parts:
```
Exclui qualquer app cujo path passe por `site-packages` — mesmo com o venv dentro do repo — **sem
enfraquecer** a detecção de strings REAIS do projeto (apps locais não passam por site-packages).
*Opção mais robusta, se preferir:* excluir também paths sob `sys.prefix` / `site.getsitepackages()`
(cobre venv com nome exótico). Sua escolha de engenharia.

## Teste de regressão (OBRIGATÓRIO — pra nunca voltar)
Adicione em `chips/tests_i18n.py` um teste que garanta que **um caminho de site-packages nunca entra
na extração** — mesmo estando sob o BASE_DIR. Ex.: simular um app-config com `path` em
`<BASE_DIR>/venv/.../site-packages/django/contrib/auth` e afirmar que `_local_app_paths()` (ou
`extract_django()`) o ignora. É o análogo do golden: prova que venv-no-repo não suja mais o portão.

## NÃO afrouxe o trabalho real do portão
Ele TEM que continuar pegando **string de PROJETO marcada e não traduzida** (a trava anti-"esqueci",
I18N.md §7 regra 8). O fix só remove o site-packages — não mexe na completude. Depois de aplicar,
confirme que o teste que exercita "string do projeto faltando → falha" (se houver em `tests_i18n.py`)
continua funcionando (falha quando deve).

## Validar (tudo local)
1. `python manage.py check_translations` → passa limpo (0 problemas).
2. `python manage.py test chips estoque --settings=core.settings_test` → verde, incluindo o novo teste de regressão.
3. `grep -c site-packages locale/*/LC_MESSAGES/django.po` → 0 (garante que ninguém rodou um extract poluído e gravou no `.po`; se der ≠ 0, rode a rotina de extração do I18N.md §6 pra limpar).

## Escopo / handoff
Mexe SÓ em `chips/i18n_source.py` (o fix) + `chips/tests_i18n.py` (o teste). É `.py` → **edita local,
valida, e ENTREGA ao dono** pra ele commitar + publicar (regra de ouro #1: o agente edita, o dono roda).
Não toque em gramática, known_parts, catálogos `.po` (estão limpos) nem outras áreas.
