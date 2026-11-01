# Prázdný stav (EmptyState)

What a list, table or area says when it has nothing: an icon, one line saying what would be here, and the one action that puts the first item here. Dashed `border-strong`, radius 6.

**Intentional addition:** neither prototype draws a general empty state (Audit draws one inline row). The product has `states.tsx:44` Empty (15 importers) and workbench `.empty`; v2 merges them into this one form.

**Rule** never only "Nic tu není": say why and how ("Zatím žádné znalosti. Přidejte podklady klienta nebo je navrhněte ze studie.").
