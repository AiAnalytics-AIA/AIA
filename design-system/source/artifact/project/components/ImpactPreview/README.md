# ImpactPreview

Shows an edit's consequences before it is committed: kept vs reopened stages, artifacts kept, cost and time.

**The consumer provides:** `lifecycle`, `stageIds`, `field` (what is being edited), `preview` (the domain ImpactPreview dict), `artifactsKept`, `costEstimate` [lo, hi] + `costBasis`, `timeEstimate` (null → chybí).

**Use:** Every edit of a material field routes through it.

**Don't:** Never commit an edit without it. Never show an estimate the server did not provide.
