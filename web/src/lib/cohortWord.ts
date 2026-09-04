/**
 * #171 -- the only cohort words on the surface are citizen · admin · nothing.
 * Display only: derive_cohort, the gates, citz ids and tier strings are
 * untouched; "controller" / "founding" / "all" leave the surface here.
 *   is_controller      -> "admin"
 *   member_number set  -> "citizen"
 *   else               -> "\u2014"
 */
export interface CohortWordInput {
  member_number?: number | null;
  controller?: boolean | null;
}

export function cohortWord(x: CohortWordInput | null | undefined): string {
  if (!x) return "\u2014";
  if (x.controller) return "admin";
  if (typeof x.member_number === "number") return "citizen";
  return "\u2014";
}
