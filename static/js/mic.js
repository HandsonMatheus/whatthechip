/* =============================================================================
   mic.js — WhatTheChip? · Reconhecimento de voz para Part Number
   Versão 1.1 · PT-BR como língua principal · EN como fallback
   =============================================================================
   USO:
     <button data-mic-target="pn-input"
             data-mic-hint="id-do-hint"
             data-mic-cta="id-do-botão-confirmar">
     </button>

   data-mic-target  (obrigatório) — id do input que receberá o PN
   data-mic-hint    (opcional)    — id do elemento de dica (ex: pn-hint)
                                    Após reconhecimento: exibe "↵ Pressione Enter"
   data-mic-cta     (opcional)    — id do botão de confirmação (Decodificar/etc.)
                                    Após reconhecimento: flash visual para chamar atenção

   SUPORTE: Chrome / Edge (full) · Safari 17+ (partial) · Firefox (não suporta)
   ============================================================================= */

(function () {
  'use strict';

  // ── i18n (I18N.md §6/§8.4): window.gettext vem do JavaScriptCatalog
  // (<script src="{% url 'javascript-catalog' %}">, incluído ANTES deste arquivo
  // nos bases). Shim fail-open: sem catálogo, devolve o pt-br original.
  // ⚠ O WORD_MAP abaixo é DADO (fonética de ditado), NUNCA passa por gettext.
  var gettext = (typeof window.gettext === 'function')
    ? window.gettext
    : function (s) { return s; };

  // ── Mapeamento: palavras faladas → caractere de PN ──────────────────────────
  var WORD_MAP = {
    // Dígitos PT-BR
    'zero':    '0',
    'um':      '1', 'hum': '1',
    'dois':    '2',
    'tres':    '3', 'três': '3',
    'quatro':  '4',
    'cinco':   '5',
    'seis':    '6',
    'sete':    '7',
    'oito':    '8',
    'nove':    '9',
    // Dígitos EN (fonética comum + inglês puro)
    'one':     '1', 'won': '1',
    'two':     '2', 'to': '2', 'too': '2',
    'three':   '3',
    'four':    '4', 'for': '4', 'fore': '4',
    'five':    '5',
    'six':     '6',
    'seven':   '7',
    'eight':   '8', 'ate': '8',
    'nine':    '9',
    // Separador
    'traco':   '-', 'hifen': '-', 'hífen': '-', 'traço': '-', 'dash': '-',
  };

  // ── Grammar JSGF — direciona o motor para fonemas alfanuméricos ─────────────
  var GRAMMAR_PT =
    '#JSGF V1.0 UTF-8 pt;\n' +
    'grammar pn;\n' +
    'public <pn> = (<tok>)+ ;\n' +
    '<tok> = a|b|c|d|e|f|g|h|i|j|k|l|m|n|o|p|q|r|s|t|u|v|w|x|y|z' +
    '|zero|um|hum|dois|três|tres|quatro|cinco|seis|sete|oito|nove' +
    '|one|two|three|four|five|six|seven|eight|nine ;';

  // ── Normalização: transcrição bruta → string de PN ─────────────────────────
  function normalise(text) {
    var t = text.toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '');          // remove diacríticos

    return t.split(/\s+/).map(function (w) {
      if (w in WORD_MAP) return WORD_MAP[w];
      return w.replace(/[^a-z0-9\-]/g, '');
    }).join('').toUpperCase().replace(/[^A-Z0-9\-]/g, '');
  }

  // ── Áudio: Web Audio API ────────────────────────────────────────────────────
  var _ac = null;

  function getAc() {
    if (!_ac) {
      try { _ac = new (window.AudioContext || window.webkitAudioContext)(); }
      catch (e) { return null; }
    }
    if (_ac.state === 'suspended') _ac.resume();
    return _ac;
  }

  function tone(freq, dur, vol) {
    var ctx = getAc(); if (!ctx) return;
    try {
      var osc  = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(vol || 0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + dur + 0.02);
    } catch (e) {}
  }

  function beepStart()   { tone(520, 0.10, 0.12); }
  function beepOk()      { tone(660, 0.08, 0.12); setTimeout(function () { tone(880, 0.12, 0.10); }, 90); }
  function beepErr()     { tone(320, 0.14, 0.12); setTimeout(function () { tone(220, 0.18, 0.09); }, 130); }

  // ── Ícones / indicadores HTML ───────────────────────────────────────────────
  var ICONS = {
    // Microfone estático — estado idle
    mic:
      '<svg class="mic-icon__svg" width="18" height="18" viewBox="0 0 24 24"' +
      ' fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>' +
      '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>' +
      '<line x1="12" y1="19" x2="12" y2="22"/></svg>',

    // 3 barras CSS animadas — estado listening (equalizador de áudio)
    listening:
      '<span class="mic-bars" aria-hidden="true">' +
      '<span class="mic-bar"></span>' +
      '<span class="mic-bar"></span>' +
      '<span class="mic-bar"></span>' +
      '</span>',

    // Check — estado ok
    ok:
      '<svg class="mic-icon__svg" width="18" height="18" viewBox="0 0 24 24"' +
      ' fill="none" stroke="currentColor" stroke-width="2.5"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<polyline points="20 6 9 17 4 12"/></svg>',

    // Enter — complementa o ok (aparece junto com a dica)
    enter:
      '<svg class="mic-icon__svg" width="18" height="18" viewBox="0 0 24 24"' +
      ' fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<polyline points="9 10 4 15 9 20"/>' +
      '<path d="M20 4v7a4 4 0 0 1-4 4H4"/></svg>',

    // X — estado erro
    err:
      '<svg class="mic-icon__svg" width="18" height="18" viewBox="0 0 24 24"' +
      ' fill="none" stroke="currentColor" stroke-width="2.5"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<line x1="18" y1="6" x2="6" y2="18"/>' +
      '<line x1="6" y1="6" x2="18" y2="18"/></svg>',

    // Spinner — estado processing
    spin: '<span class="mic-icon__spin" aria-hidden="true"></span>',
  };

  // ── Estado visual do botão ──────────────────────────────────────────────────
  function setState(btn, state) {
    btn.classList.remove('is-listening', 'is-processing', 'is-ok', 'is-err');
    btn.dataset.micState = state;
    var iconWrap = btn.querySelector('.mic-icon');

    switch (state) {
      case 'listening':
        btn.classList.add('is-listening');
        if (iconWrap) iconWrap.innerHTML = ICONS.listening;
        btn.title = gettext('Ouvindo… clique para parar');
        btn.setAttribute('aria-label', gettext('Gravando — clique para parar'));
        break;

      case 'processing':
        btn.classList.add('is-processing');
        if (iconWrap) iconWrap.innerHTML = ICONS.spin;
        btn.title = gettext('Processando…');
        break;

      case 'ok':
        btn.classList.add('is-ok');
        if (iconWrap) iconWrap.innerHTML = ICONS.enter;   // ↵ enter convida o usuário
        btn.title = gettext('Reconhecido — pressione Enter');
        setTimeout(function () { setState(btn, 'idle'); }, 3000);
        break;

      case 'err':
        btn.classList.add('is-err');
        if (iconWrap) iconWrap.innerHTML = ICONS.err;
        btn.title = gettext('Não reconhecido — tente novamente');
        setTimeout(function () { setState(btn, 'idle'); }, 2000);
        break;

      default: // idle
        if (iconWrap) iconWrap.innerHTML = ICONS.mic;
        btn.title = gettext('Fale o Part Number');
        btn.setAttribute('aria-label', gettext('Ativar reconhecimento de voz'));
        break;
    }
  }

  // ── Injeção de valor no input ───────────────────────────────────────────────
  function injectValue(input, value) {
    input.value = value;
    input.dispatchEvent(new Event('input',  { bubbles: true, cancelable: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    try { input.focus(); } catch (e) {}
  }

  // ── Dica "Pressione Enter" após reconhecimento ──────────────────────────────
  // Usa data-mic-hint="<id>" no botão para apontar o elemento de hint.
  function showEnterHint(btn) {
    var hintId = btn.dataset.micHint;
    if (!hintId) return;
    var el = document.getElementById(hintId);
    if (!el) return;

    var origText  = el.textContent;
    var origClass = el.className;

    el.textContent = '↵  ' + gettext('PN reconhecido — pressione Enter para confirmar');
    el.classList.add('wtc-mic-hint--active');

    setTimeout(function () {
      el.textContent = origText;
      el.className   = origClass;
    }, 3000);   // mesmo tempo que o estado is-ok
  }

  // ── Dispara a busca automaticamente após reconhecimento ────────────────────
  // Estratégia 1: clica no botão CTA apontado por data-mic-cta="<id>"
  // Estratégia 2 (fallback): despacha Enter no input (funciona quando há
  //   um keydown listener no input, como na home page)
  function triggerSearch(btn, input) {
    var ctaId = btn.dataset.micCta;
    if (ctaId) {
      var cta = document.getElementById(ctaId);
      if (cta && !cta.disabled) {
        // Flash visual primeiro, depois clica
        cta.classList.add('wtc-mic-cta-flash');
        setTimeout(function () {
          cta.classList.remove('wtc-mic-cta-flash');
          cta.click();
        }, 350);
        return;
      }
    }
    // Fallback: Enter no input
    input.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter', code: 'Enter', keyCode: 13,
      bubbles: true, cancelable: true
    }));
  }

  // ── Acopla microfone a um botão ─────────────────────────────────────────────
  function attachMic(btn) {
    var targetId = btn.dataset.micTarget;
    if (!targetId) return;

    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      btn.hidden = true;
      btn.setAttribute('aria-hidden', 'true');
      return;
    }

    if (!btn.querySelector('.mic-icon')) {
      btn.innerHTML = '<span class="mic-icon"></span>';
    }
    setState(btn, 'idle');

    var rec    = null;
    var active = false;

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();

      if (active) {
        if (rec) rec.stop();
        return;
      }

      var input = document.getElementById(targetId);
      if (!input) return;

      rec = new SR();

      // Grammar hint — reduz vocabulário para alfanumérico PT-BR
      var SGL = window.SpeechGrammarList || window.webkitSpeechGrammarList;
      if (SGL) {
        try {
          var list = new SGL();
          list.addFromString(GRAMMAR_PT, 1);
          rec.grammars = list;
        } catch (e) {}
      }

      rec.lang            = 'pt-BR';
      rec.continuous      = false;
      rec.interimResults  = true;     // ← resultados parciais em tempo real
      rec.maxAlternatives = 5;

      rec.onstart = function () {
        active = true;
        beepStart();
        setState(btn, 'listening');
      };

      rec.onresult = function (ev) {
        var result     = ev.results[0];
        var transcript = result[0].transcript;

        if (!result.isFinal) {
          // ── Resultado parcial: mostra em tempo real sem mudar o estado ─────
          var partial = normalise(transcript);
          if (partial.length > 0) {
            input.value = partial;
            input.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
          }
          return;
        }

        // ── Resultado final: escolhe a melhor alternativa normalizada ─────────
        setState(btn, 'processing');

        var best = '';
        for (var i = 0; i < result.length; i++) {
          var candidate = normalise(result[i].transcript);
          if (candidate.length > best.length) best = candidate;
        }

        if (best.length >= 1) {
          injectValue(input, best);
          beepOk();
          setState(btn, 'ok');
          triggerSearch(btn, input);
        } else {
          beepErr();
          setState(btn, 'err');
        }
      };

      rec.onerror = function (ev) {
        active = false;
        if (ev.error === 'no-speech') {
          setState(btn, 'idle');
        } else {
          beepErr();
          setState(btn, 'err');
        }
      };

      rec.onend = function () {
        active = false;
        if (btn.dataset.micState === 'listening') {
          setState(btn, 'idle');
        }
      };

      rec.start();
    });
  }

  // ── Init ─────────────────────────────────────────────────────────────────────
  function init() {
    document.querySelectorAll('[data-mic-target]').forEach(function (btn) {
      attachMic(btn);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
