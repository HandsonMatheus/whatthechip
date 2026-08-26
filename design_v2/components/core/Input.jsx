import React from "react";

/* Carbon: o campo é uma chapa rebaixada com UMA régua embaixo, cantos 0px, e o foco é um contorno
   de 2px rente à borda. Antes daqui saía uma caixa arredondada (--r-md) de 1px com halo suave de
   4px — a linguagem do sistema anterior; nenhum campo do produto se parece com aquilo.
   A chapa é --surface-2, nunca --ink-05 cru: os aliases semânticos são remapeados em
   [data-theme="dark"], os degraus da rampa não. Um valor cru da rampa aqui deixa o campo
   ilegível no tema escuro. */
export function Input({ mono = false, invalid = false, style = {}, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  const rule = invalid ? "var(--red-60)" : (focus ? "var(--blue-60)" : "var(--ink-50)");
  return (
    <input {...rest}
      onFocus={(e) => { setFocus(true); rest.onFocus && rest.onFocus(e); }}
      onBlur={(e) => { setFocus(false); rest.onBlur && rest.onBlur(e); }}
      style={{
        width: "100%", height: "var(--ctl-md)", padding: "0 16px",
        fontSize: mono ? 16 : 14,
        fontFamily: mono ? "var(--mono)" : "var(--sans)",
        letterSpacing: mono ? ".04em" : "0",
        textTransform: mono ? "uppercase" : "none",
        color: "var(--text)", background: "var(--surface-2)",
        border: 0, borderBottom: "1px solid " + rule, borderRadius: 0,
        outline: focus ? "2px solid var(--blue-60)" : "none", outlineOffset: "-2px",
        transition: "border-color var(--dur-1)",
        ...style
      }} />
  );
}
