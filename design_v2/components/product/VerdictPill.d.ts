export interface VerdictPillProps {
  /** Which profitability outcome. @default "rentavel" */
  verdict?: "rentavel" | "nao" | "indeterminado";
  /** Show the 6px square status marker. @default true */
  showDot?: boolean;
  /** Override label text. */
  children?: React.ReactNode;
}
/**
 * Carbon status tag for the profitability verdict (RENTÁVEL / NÃO RENTÁVEL / INDETERMINADO):
 * 0px corners, 11px/800 label, 6px square marker.
 * @startingPoint section="Components" subtitle="Verdict tag" viewport="700x120"
 */
export function VerdictPill(props: VerdictPillProps): JSX.Element;
