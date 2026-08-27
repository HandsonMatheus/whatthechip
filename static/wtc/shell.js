/* WhatTheChip — consolidação do cabeçalho do comprador.

   Adaptado de `design_v2/ui_kits/whatthechip/shell.js` em 2026-08-27.

   ⚠ POR QUE ISTO EXISTE. O `partner_base.html` trazia um comentário afirmando
   que "o `.me` é o widget de perfil que o shell.js do sistema MONTA — e o
   shell.js não vem no pacote". Estava errado: o `shell.js` vem no `front.zip`,
   em `dist/comprador/`. Só o `design_system.zip` não o traz, porque ele é
   comportamento de tela, não folha de estilo. Por causa desse engano o
   cabeçalho ficou com sete células soltas disputando largura — empresa,
   usuário, sino, tema, idioma e sair — que é exatamente o que o arquivo
   original abre dizendo que veio consertar.

   O que ele faz: empresa, usuário, IDIOMA e SAIR passam a viver num único
   botão de perfil com gaveta. A barra fica com cinco zonas — marca · nav ·
   câmbio · sino · perfil. O TEMA não desce para a gaveta: é ação de um toque,
   usada a qualquer momento, e enterrá-la em dois toques custava mais que
   valia (decisão do design, mantida).

   DIFERENÇAS OBRIGATÓRIAS em relação ao arquivo do kit, todas por causa do
   Django e nenhuma por gosto:

   1. Os botões de idioma do protótipo são falsos — só trocam uma classe.
      Aqui cada um SUBMETE o formulário de `set_language`, que grava o cookie
      e, logado, a preferência da conta. A lista de idiomas não é fixa no
      código: sai do `<select>` que o `partials/lang_select.html` já renderiza,
      então quem manda continua sendo `settings.LANGUAGES`.

   2. O "sair" do kit é um `<a href>`. Aqui é um `<form method="post">` com
      CSRF — logout por GET é falha de segurança. Movemos o FORMULÁRIO
      inteiro, não só o botão, senão o POST perde o `action` e o token.

   3. Os elementos são MOVIDOS, não recriados, como no original: o
      `theme.js` continua ligado ao `#theme-btn` e o `<select>` de idioma
      continua sendo o que o Django renderizou. */
(function () {
  "use strict";

  var POPS = ['.me'];
  function fecharTodos(exceto) {
    document.querySelectorAll('.me.on').forEach(function (n) {
      if (n === exceto) return;
      n.classList.remove('on');
      var t = n.querySelector('[aria-expanded]');
      if (t) t.setAttribute('aria-expanded', 'false');
    });
  }

  function perfil(shell) {
    if (shell.querySelector('.me')) return;
    var who = shell.querySelector('.pshell__who');
    var langForm = shell.querySelector('[data-lang-form]');
    var sel = langForm && langForm.querySelector('select[name="language"]');
    var out = shell.querySelector('.shell__ico--out');
    var outForm = out && out.form;
    if (!who) return;

    var me = document.createElement('div');
    me.className = 'me';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'me__btn';
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', shell.dataset.meLabel || 'Conta e preferências');
    var pop = document.createElement('div');
    pop.className = 'me__pop';
    me.appendChild(btn);
    me.appendChild(pop);

    // O botão guarda só o avatar; nome e cargo moram na gaveta — assim a
    // barra não disputa largura com a nav e a identidade fica sempre legível
    // ao abrir.
    var av = who.querySelector('.pshell__av');
    var usr = who.querySelector('.pshell__u');
    if (av) btn.appendChild(av);
    var chev = document.createElement('span');
    chev.className = 'me__chev';
    chev.innerHTML = '<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
    btn.appendChild(chev);

    if (usr) {
      var hd = document.createElement('div');
      hd.className = 'me__hd';
      hd.appendChild(usr);
      pop.appendChild(hd);
    }
    who.remove();

    // ── idioma ──
    if (sel) {
      var sec = document.createElement('div');
      sec.className = 'me__sec';
      var lbl = document.createElement('div');
      lbl.className = 'me__l';
      lbl.textContent = langForm.dataset.langLabel || 'Idioma';
      sec.appendChild(lbl);
      var box = document.createElement('div');
      box.className = 'me__langs';
      Array.prototype.forEach.call(sel.options, function (op) {
        var b = document.createElement('button');
        b.type = 'button';
        // O rótulo curto vem do próprio código do idioma: `zh-hans` → 中文,
        // o resto → as duas primeiras letras. Sem tabela fixa: um idioma novo
        // no settings aparece aqui sozinho.
        b.textContent = op.value.slice(0, 2) === 'zh'
          ? '中文' : op.value.slice(0, 2).toUpperCase();
        b.title = op.textContent.trim();
        if (op.selected) b.className = 'on';
        b.onclick = function () {
          sel.value = op.value;
          langForm.submit();
        };
        box.appendChild(b);
      });
      sec.appendChild(box);
      pop.appendChild(sec);
      // O <select> sai da barra mas continua VIVO dentro do formulário, que é
      // quem carrega o action e o CSRF. Esconder é de propósito: sem JS ele
      // reaparece e a tela continua trocando de idioma.
      langForm.hidden = true;
      pop.appendChild(langForm);
    }

    // ── sair ──
    if (outForm) pop.appendChild(outForm);
    else if (out) pop.appendChild(out);

    shell.appendChild(me);

    btn.onclick = function (e) {
      e.stopPropagation();
      var abrir = !me.classList.contains('on');
      fecharTodos(me);
      me.classList.toggle('on', abrir);
      btn.setAttribute('aria-expanded', abrir ? 'true' : 'false');
    };
    pop.onclick = function (e) { e.stopPropagation(); };
    document.addEventListener('click', function () { fecharTodos(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') fecharTodos();
    });
  }

  // ── gaveta de tablet/telefone ──
  // A barra MEDE A SI MESMA e classifica a largura. Medir o elemento e não a
  // janela faz a mesma regra valer no aparelho e dentro de um enquadramento.
  var BP = { phone: 600, tablet: 880 };
  function gaveta(shell) {
    if (shell.querySelector('.shell__burger')) return;
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'shell__burger';
    b.setAttribute('aria-label', shell.dataset.menuLabel || 'Menu');
    b.setAttribute('aria-expanded', 'false');
    b.innerHTML = '<i></i><i></i><i></i>';
    var ancora = shell.querySelector('.pshell__spacer');
    if (ancora && ancora.nextSibling) shell.insertBefore(b, ancora.nextSibling);
    else shell.appendChild(b);
    b.addEventListener('click', function (e) {
      e.stopPropagation();
      var abrir = !shell.classList.contains('is-open');
      shell.classList.toggle('is-open', abrir);
      b.setAttribute('aria-expanded', abrir ? 'true' : 'false');
    });
    function medir() {
      var w = shell.offsetWidth || window.innerWidth;
      if (w <= BP.phone) shell.dataset.shell = 'phone';
      else if (w <= BP.tablet) shell.dataset.shell = 'tablet';
      else {
        delete shell.dataset.shell;
        shell.classList.remove('is-open');
        b.setAttribute('aria-expanded', 'false');
      }
    }
    medir();
    window.addEventListener('resize', medir);
  }

  function boot() {
    var shell = document.querySelector('.pshell');
    if (!shell) return;
    perfil(shell);
    gaveta(shell);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }
})();
