import * as React from "react";
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Part-Number style: IBM Plex Mono, uppercased. @default false */
  mono?: boolean;
  /** Turns the bottom rule red. @default false */
  invalid?: boolean;
}
/**
 * Carbon text field: rebated slab (--surface-2), a single 1px bottom rule that turns blue on
 * focus, square corners, inset 2px focus outline. mono variant for Part Numbers.
 */
export function Input(props: InputProps): JSX.Element;
