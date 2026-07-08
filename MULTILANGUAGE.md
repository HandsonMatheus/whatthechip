# MULTILANGUAGE.md — O WhatTheChip em 4 idiomas

> **Documento de FEATURE** — descreve o sistema multilíngue do ponto de vista
> do produto: o que existe, como se comporta e como se opera. É a peça que
> entra na documentação geral do sistema. A **bíblia técnica** (arquitetura,
> rotina de tradução, armadilhas de código) é o **`I18N.md`** — em conflito,
> o código vence, depois o I18N.md, depois este. Convenção de engenharia:
> `CLAUDE.md` §6 ("Convenção i18n").
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
idioma novo ≈ catálogos de tradução + arquivos de conteúdo (ver §7).

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

## 7. Como adicionar um idioma novo (visão de produto)

1. Ativar o idioma na configuração (1 linha em `settings.LANGUAGES`).
2. Gerar e traduzir os 2 catálogos (`django.po` + `djangojs.po`) pela rotina §6.
3. Traduzir os arquivos de conteúdo que importarem (no mínimo a home).
4. `check_translations` verde → commit → deploy.

Sem migração, sem mudança de template ou engine: os seletores, o modelo de
preferência e a detecção leem a lista de idiomas da configuração. Custo real ≈
o volume de texto a traduzir.

---

## 8. Limitações conhecidas / fila

- **Páginas de fabricante** (`fab-samsung`…, `fabricantes`, `contato`):
  conteúdo ainda em PT (fallback), traduzir sob demanda de mercado.
- **Fragmentos técnicos do decode** (ex.: `"por die"`, `"consultar datasheet"`
  dentro de strings compostas do engine): aparecem em PT em qualquer idioma até
  a tokenização do vocabulário do engine (planejada; ver `I18N.md` §5.1).
- **Histórico persistido** (motivos de reprovação já gravados, exportações):
  exibido no canônico pt-br; rótulo traduzido on-read é evolução futura.

---

## 9. Ponteiros técnicos (para quem for mexer)

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
