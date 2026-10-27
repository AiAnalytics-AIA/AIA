# Kontrola změn (ChangeReview)

Every edit the Lead or an AI proposal makes is shown as its own change:
- the field's name;
- the old words struck through and the new words inserted;
- **Ponechat** and **Vrátit** for this change alone, plus "Ponechat vše" for the turn.

Accepted text edits under the person's auto-accept read "Přijato automaticky" with Vrátit (the replaced wording written back as the person's edit).

**Rules**
- A change whose base moved is refused at the item: "Položka se mezitím změnila", never merged blind (`StaleProposal`).
- Structure (a new question, a deleted section) never auto-accepts.
- After Ponechat, the item flashes its target on the stage (`data-aia`) so the person sees where it went.
