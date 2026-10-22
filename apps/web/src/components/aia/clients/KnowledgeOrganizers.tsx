"use client";

// The library's folders and labels as rows of its side panel (input-interactions chunk 2, audit
// D1-D7): each is chosen by its row, renamed where its name is shown (F2, a double click or its
// ⋯ menu opens the name in place: I1), a label recoloured by its swatch (I3, I5), and either
// deleted from the menu -- at once, with "Vrátit" (I6), unless its items could not all be read
// first, when the row asks instead, naming what goes. "+ Nová složka / Nový štítek" are rows of
// the list (I5). No modal anywhere: the person stays in the list they are organizing.

import { type KeyboardEvent, type ReactNode, type Ref, useEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type KnowledgeFolder, type KnowledgeLabel, LABEL_COLOURS, type LabelColour } from "@/lib/api";
import type { TextRules } from "@/lib/inline-edit";
import { LABEL_DOT } from "@/lib/knowledge-library";
import { NAME_MAX, nameProblem, nameProblemWords } from "@/lib/name-input";
import { InlineConfirm } from "../../rehome/step";
import { InlineCreateRow } from "../../ui/InlineCreateRow";
import { InlineText } from "../../ui/InlineText";
import { MenuButton } from "../../ui/MenuButton";
import { SwatchPicker } from "../../ui/SwatchPicker";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

export function NavButton({
  on, onClick, children, count, attention = false, disabled = false, buttonRef, onKeyDown, onDoubleClick,
}: {
  on: boolean;
  onClick: () => void;
  children: ReactNode;
  count?: number | null;
  attention?: boolean;
  disabled?: boolean;
  buttonRef?: Ref<HTMLButtonElement>;
  onKeyDown?: (e: KeyboardEvent<HTMLButtonElement>) => void;
  onDoubleClick?: () => void;
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      aria-pressed={on}
      disabled={disabled}
      onClick={onClick}
      onKeyDown={onKeyDown}
      onDoubleClick={onDoubleClick}
      className={`flex min-h-9 w-full min-w-0 items-center gap-2 rounded-control px-2 text-left text-[13px] disabled:opacity-50 ${FOCUS} ${on ? "bg-signal-wash font-semibold text-signal" : "text-ink hover:bg-surface-sunken"}`}
    >
      <span className="min-w-0 flex-1 truncate">{children}</span>{" "}
      {count != null && count > 0 ? (
        <span className={`rounded-pill px-1.5 font-mono text-[11px] ${attention ? "bg-status-you text-ink" : "text-ink-faint"}`}>{count}</span>
      ) : null}
    </button>
  );
}

/** A folder's or a label's new name, checked at the field as the server will (organizer_name / _key). */
function nameRules(names: readonly string[], own: string): TextRules {
  return {
    maxLength: NAME_MAX,
    validate: (value) => {
      const problem = nameProblem(value, names, NAME_MAX, own);
      return problem ? nameProblemWords(problem) : null;
    },
  };
}

/** What a person who may file knowledge can do to a folder or a label. */
export type OrganizerEdit = {
  /** Every name in the same list, its own included, for the uniqueness check at the field. */
  names: readonly string[];
  /** Saves a new name; a rejection is "Neuloženo – Zkusit znovu" at the field. */
  rename: (name: string) => Promise<unknown>;
  /** Asked from the menu: deletes with undo, or asks at the row (`confirm`). */
  remove: () => void;
  /** Set when the row asks before deleting: what goes, in words. */
  confirm: string | null;
  onConfirm: () => void;
  onKeep: () => void;
};

/**
 * A rename just saved, shown until the list read again says it: the field closes on the save's
 * answer, and the row would show the old name for the moment the list takes to come back.
 */
function useJustNamed(name: string): [string, (to: string) => void] {
  const [named, setNamed] = useState<{ from: string; to: string } | null>(null);
  return [named && named.from === name ? named.to : name, (to) => setNamed({ from: name, to })];
}

function useRenaming(edit: OrganizerEdit | undefined) {
  const [renaming, setRenaming] = useState(false);
  const row = useRef<HTMLButtonElement>(null);
  // Back to the row, and focus with it (I11: focus returns where the person was). Focused once
  // the render that brings the row back has committed: a frame scheduled at `stop` can run
  // before that render, find no row, and leave focus on the page (seen on a loaded CI runner).
  // Only focus left with the closed field, on the page, comes back: a slow save's answer must not
  // take it from wherever the person went meanwhile (another label's colours, a CI flake).
  const refocus = useRef(false);
  useEffect(() => {
    if (renaming || !refocus.current) return;
    refocus.current = false;
    const now = document.activeElement;
    if (now && now !== document.body) return;
    row.current?.focus();
  }, [renaming]);
  return {
    renaming: !!edit && renaming,
    start: () => setRenaming(true),
    stop: () => {
      refocus.current = true;
      setRenaming(false);
    },
    row,
    // F2 on the row opens its name in place, as on any shown value (I1); Enter stays the row's own.
    onKeyDown: edit
      ? (e: KeyboardEvent<HTMLButtonElement>) => {
          if (e.key !== "F2") return;
          e.preventDefault();
          setRenaming(true);
        }
      : undefined,
  };
}

function Confirm({ edit }: { edit: OrganizerEdit }) {
  if (!edit.confirm) return null;
  return (
    <div className="px-2 pb-1 pt-0.5">
      <InlineConfirm message={edit.confirm} action={t("aia.library.deleteAction")} onConfirm={edit.onConfirm} onCancel={edit.onKeep} />
    </div>
  );
}

export function FolderRow({ folder, on, onPick, edit }: { folder: KnowledgeFolder; on: boolean; onPick: () => void; edit?: OrganizerEdit }) {
  const r = useRenaming(edit);
  const [name, named] = useJustNamed(folder.name);
  if (edit && r.renaming) {
    return (
      <div className="px-2 py-0.5">
        <InlineText
          autoOpen
          value={name}
          label={t("aia.library.folderName")}
          rules={nameRules(edit.names, folder.name)}
          onCommit={(next) => edit.rename(next).then(() => named(next))}
          onSettled={r.stop}
          className="w-full"
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col">
      <div className="flex min-w-0 items-center gap-0.5">
        <NavButton buttonRef={r.row} on={on} onClick={onPick} count={folder.item_count} onKeyDown={r.onKeyDown} onDoubleClick={edit ? r.start : undefined}>
          {name}
        </NavButton>
        {edit ? (
          <MenuButton
            hideLabel
            align="end"
            label={tv("aia.library.folderActions", { name })}
            items={[
              { key: "rename", label: t("aia.library.rename") },
              { key: "delete", label: t("aia.library.deleteFolder") },
            ]}
            onSelect={(k) => (k === "rename" ? r.start() : edit.remove())}
          />
        ) : null}
      </div>
      {edit ? <Confirm edit={edit} /> : null}
    </div>
  );
}

export function LabelRow({
  label, on, onPick, disabled = false, edit, recolour,
}: {
  label: KnowledgeLabel;
  on: boolean;
  onPick: () => void;
  /** Labels do not filter Ke schválení. */
  disabled?: boolean;
  edit?: OrganizerEdit;
  recolour?: (colour: LabelColour) => void;
}) {
  const r = useRenaming(edit);
  const [name, named] = useJustNamed(label.name);
  if (edit && r.renaming) {
    return (
      <div className="px-2 py-0.5">
        <InlineText
          autoOpen
          value={name}
          label={t("aia.library.labelName")}
          rules={nameRules(edit.names, label.name)}
          onCommit={(next) => edit.rename(next).then(() => named(next))}
          onSettled={r.stop}
          className="w-full"
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col">
      <div className="flex min-w-0 items-center gap-0.5">
        {edit && recolour ? (
          <SwatchPicker
            popover
            value={label.colour}
            colours={LABEL_COLOURS}
            swatch={LABEL_DOT}
            name={(c) => t(`aia.library.colours.${c}`)}
            label={tv("aia.library.labelColourOf", { name })}
            onChange={recolour}
          />
        ) : (
          <span aria-hidden="true" className={`mx-2.5 size-[7px] shrink-0 rounded-full ${LABEL_DOT[label.colour]}`} />
        )}
        <NavButton buttonRef={r.row} on={on} onClick={onPick} disabled={disabled} count={label.item_count} onKeyDown={r.onKeyDown} onDoubleClick={edit ? r.start : undefined}>
          {name}
        </NavButton>
        {edit ? (
          <MenuButton
            hideLabel
            align="end"
            label={tv("aia.library.labelActions", { name })}
            items={[
              { key: "rename", label: t("aia.library.rename") },
              { key: "delete", label: t("aia.library.deleteLabel") },
            ]}
            onSelect={(k) => (k === "rename" ? r.start() : edit.remove())}
          />
        ) : null}
      </div>
      {edit ? <Confirm edit={edit} /> : null}
    </div>
  );
}

/** "+ Nový štítek": a row of the list with its swatch beside the name; Enter creates it in that colour. */
export function NewLabelRow({
  existing, suggested, onCreate,
}: {
  existing: readonly string[];
  /** The colour it starts with (nextLabelColour). */
  suggested: LabelColour;
  /** Resolves to nothing when created, or to the refusal in words, said at the row. */
  onCreate: (name: string, colour: LabelColour) => Promise<string | void>;
}) {
  // The swatch starts on the suggestion; a colour the person picks holds until that label is
  // created, and the next row starts on the next suggestion.
  const [chosen, setChosen] = useState<LabelColour | null>(null);
  const colour = chosen ?? suggested;
  return (
    <InlineCreateRow
      label={t("aia.library.newLabel")}
      icon="tag"
      existing={existing}
      onCreate={(name) =>
        onCreate(name, colour).then((refusal) => {
          if (refusal === undefined) setChosen(null);
          return refusal;
        })
      }
      adornment={
        <SwatchPicker
          popover
          align="end"
          value={colour}
          colours={LABEL_COLOURS}
          swatch={LABEL_DOT}
          name={(c) => t(`aia.library.colours.${c}`)}
          label={t("aia.library.newLabelColour")}
          onChange={setChosen}
        />
      }
    />
  );
}
