# Poznámka (Note)

A box that says something about the page: radius 6, 10 × 12 padding, 13 px, an icon first. Four tones only.

- plain (surface ground): information.
- `you` (coral): something this person must do.
- `bad` (fault): failed or refused, with the reason in words and the way out.
- `sig` (signal tint): context the person should read (which version an edit starts from).
- `ai` (AI wash): what the Lead or a model wrote, never evidence.

**Rules** no amber or green notes; a note that waits on someone else is plain with the slate word; a failure says what failed, why, and the next step, never "Něco se pokazilo".

**Replaces** 244 hand-rolled boxes (fault-wash ×38 in 25 files, you-wash ×37 in 20, signal-tint ×14 in 9), `live/ui.tsx:76` ErrorNote (amber), `states.tsx:29` Loaded's failed box (r8 p-5), `useAiStep.tsx:156` AiFailureCard and `useAnalysis.tsx:118` AnalysisFailureCard (r8), workbench `.notice`.
