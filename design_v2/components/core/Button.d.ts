import * as React from "react";
export interface ButtonProps {
  /** Visual style. @default "primary" */
  variant?: "primary" | "ghost" | "danger" | "success";
  /** Height from the control scale: sm 36 · md 48 · lg 56. @default "md" */
  size?: "sm" | "md" | "lg";
  /** Optional leading icon (SVG element). */
  iconLeft?: React.ReactNode;
  disabled?: boolean;
  children?: React.ReactNode;
  onClick?: (e: React.MouseEvent) => void;
  style?: React.CSSProperties;
}
/**
 * Primary action button — WhatTheChip Signal Blue. Square corners (Carbon).
 * @startingPoint section="Components" subtitle="Buttons" viewport="700x130"
 */
export function Button(props: ButtonProps): JSX.Element;
