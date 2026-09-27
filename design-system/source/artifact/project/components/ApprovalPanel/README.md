# ApprovalPanel

Gate approval and sign-off, including the separation-of-duties refusal.

**The consumer provides:** `what`, `fingerprint`, `producer`, `producerIsViewer`, `selfAllowed`, `policySource` (SelfApprovalSource), `eligible`, `checks` {passed,total,warnings,modelled,pending}, `audit`.

**Use:** Use it on QA gates and on report sign-off.

**Don't:** The SoD state is a designed panel, never a toast. State what the reviewer attests to, in a sentence.
