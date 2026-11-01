# Příkazová paleta (CommandPalette)

One place to go anywhere and start anything: Ctrl K / ⌘ K from every page, and the "Hledat nebo spustit…" field in the top bar of every page that has one.

**Groups, always in this order**
1. **Čeká na vás**: everything awaiting this person across clients, studies and Settings. These are the same items as the overview bar and the activity tray, with the coral pause glyph.
2. **Přejít**: clients, studies, knowledge, memory and Settings sections. A study opens on Přehled studie.
3. **Akce**: Nový výzkum, Přidat podklady, typed Lead commands ("Analyzuj zadání"), Spustit výzkum, Stáhnout zprávu. A paid action shows its ceiling as `≤ 0,40 USD`. Choosing it never pays: it opens the step where the person approves.

**Keyboard**
- Ctrl/⌘ K opens it. The field takes focus.
- ↑ ↓ move.
- Enter opens.
- Esc closes and returns focus to where it was.
- `?` shows the shortcut sheet.
- Typing filters accent-folded: "rozpocet" finds "Rozpočet".
- The shortcut is ignored when it repeats, under a modal, and in a field of another widget.

**Rules**
- Never the only way to an action, only a shorter one.
- No result reads "Nic nenalezeno pro „…“" and offers the search on Projektová paměť.
- Scope chip ("Vše", or "V tomto klientovi" inside a client) narrows; Backspace on an empty field removes it.

**Replaces** Settings' SectionMenu, which stays as the palette scoped to Settings (`settings/SectionMenu.tsx:131-143`), and the missing global Ctrl K that its footer promised ("odkudkoli").

**On the canvases** in the top bar of every board, as `details.v4-cmd`.
