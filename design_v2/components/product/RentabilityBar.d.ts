export interface RentabilityBarProps {
  /** Units judged profitable. */
  rentavel?: number;
  /** Units judged not profitable (scrap). */
  nao?: number;
  /** Units with an undetermined verdict. */
  indeterminado?: number;
  /** Show the counted legend below the bar. @default false */
  showLegend?: boolean;
  /** Bar height in px — 8 is the Carbon step used across the product. @default 8 */
  height?: number;
  /** Masked view (operator/manager): collapses "não rentável" + "indeterminado" into a single neutral "descarte" segment. @default false */
  masked?: boolean;
}
/**
 * WhatTheChip signature: a lot's composition as one 8px segmented bar — square
 * segments, 0px corners, no vertical rule.
 * @startingPoint section="Components" subtitle="Composition bar" viewport="700x160"
 */
export function RentabilityBar(props: RentabilityBarProps): JSX.Element;
