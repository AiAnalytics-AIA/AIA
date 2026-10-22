// Dimenze's ids for the Research Lead (artifact-dimensions DIM1): how the screen marks what the Lead
// can name. The stage's row in the shared registry (lib/workbench-artifacts.ts ARTIFACTS.dimensions)
// says which view operations and target kinds it has. An id outside the registry's grammar is left
// unmarked rather than breaking the screen: the Lead cannot name what has no id. The sample size's
// `sample:n` is Vzorek's (lib/artifacts/sample.ts). Pure.

import { tryAiaId } from "../workbench-artifacts";

/** A chosen dimension's row: `dimension:<id>`. */
export const dimensionAia = (id: string): string | null => tryAiaId("dimension", id);

/** One of the client's own dimensions, by its materialization run: `own_dimension:<run id>`. */
export const ownDimensionAia = (runId: string): string | null => tryAiaId("own_dimension", runId);
