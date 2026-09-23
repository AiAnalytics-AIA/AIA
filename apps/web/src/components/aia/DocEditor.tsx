"use client";

import { useEffect, useMemo, useState } from "react";
import type { JSONContent } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableHeader } from "@tiptap/extension-table-header";
import { TableCell } from "@tiptap/extension-table-cell";
import { Panel } from "@/components/ui";
import { RibbonButton, RibbonGroup } from "@/components/aia/Ribbon";
import {
  acceptProposal,
  ensureInitialDoc,
  getDocState,
  rejectProposal,
  setDocState,
} from "@/lib/doc";
import { t } from "@/i18n/t";

// DEVELOPMENT FIXTURE (registry: "report-draft"): proposals are simulated in the
// browser. The roles are the domain's model roles, not an invented agent roster.
const AGENTS = [
  { id: "report_polish_model", name: t("modelRole.report_polish_model") },
  { id: "analysis_model", name: t("modelRole.analysis_model") },
  { id: "research_model", name: t("modelRole.research_model") },
];

export function DocEditor({ studyId }: { studyId: string }) {
  const [agent, setAgent] = useState(AGENTS[0].id);
  const [chat, setChat] = useState("");
  const [refresh, setRefresh] = useState(0);

  const state = useMemo(() => {
    return getDocState(studyId) ?? ensureInitialDoc(studyId);
  }, [studyId, refresh]);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
      Placeholder.configure({
        placeholder: "Začněte psát…",
      }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: state.current as JSONContent,
    editorProps: {
      attributes: {
        class: "focus:outline-none",
      },
    },
  });

  // Keep editor content in sync when accepting/rejecting proposals.
  useEffect(() => {
    if (!editor) return;
    editor.commands.setContent(state.current as JSONContent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);

  function saveCurrent() {
    if (!editor) return;
    const json = editor.getJSON();
    setDocState(studyId, {
      ...state,
      current: json,
    });
    setRefresh((x) => x + 1);
  }

  function generateProposal() {
    if (!editor) return;

    // Snapshot current from editor (ensures we propose on latest state)
    const current = editor.getJSON();

    // Simulated assistant proposal (fixture): append a short formal Czech paragraph + a tiny table.
    const proposed = structuredClone(current) as Record<string, unknown>;

    const p = proposed as unknown as { content?: unknown[] };
    p.content = p.content || [];
    p.content.push({
      type: "heading",
      attrs: { level: 2 },
      content: [{ type: "text", text: t("docEditor.proposalHeading") }],
    });
    p.content.push({
      type: "paragraph",
      content: [
        {
          type: "text",
          text: "Navrhujeme doplnit tuto část o jasné shrnutí cíle, klíčových předpokladů a doporučených dalších kroků. Text je psán ve formální češtině.",
        },
      ],
    });
    p.content.push({
      type: "table",
      content: [
        {
          type: "tableRow",
          content: [
            { type: "tableHeader", content: [{ type: "paragraph", content: [{ type: "text", text: "Položka" }] }] },
            { type: "tableHeader", content: [{ type: "paragraph", content: [{ type: "text", text: "Poznámka" }] }] },
          ],
        },
        {
          type: "tableRow",
          content: [
            { type: "tableCell", content: [{ type: "paragraph", content: [{ type: "text", text: "Cíl" }] }] },
            { type: "tableCell", content: [{ type: "paragraph", content: [{ type: "text", text: "Upřesnit rozhodnutí, které má studie podpořit" }] }] },
          ],
        },
      ],
    });

    setDocState(studyId, {
      current,
      proposed,
      lastProposalMeta: {
        agent,
        createdAt: new Date().toISOString(),
        prompt: chat.trim() || "(bez zprávy)",
      },
    });
    setChat("");
    setRefresh((x) => x + 1);
  }

  function onAccept() {
    acceptProposal(studyId);
    setRefresh((x) => x + 1);
  }

  function onReject() {
    rejectProposal(studyId);
    setRefresh((x) => x + 1);
  }

  const hasProposal = Boolean(state.proposed);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-3">
        {/* Ribbon (Word-like) */}
        <div className="rounded-md border border-border bg-surface-raised ">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <div className="text-sm font-semibold text-ink">Dokument</div>
            <div className="flex items-center gap-2">
              {hasProposal ? <span className="inline-flex items-center rounded-sm border border-border px-1.5 text-xs text-ink-muted">{t("docEditor.proposalPending")}</span> : <span className="inline-flex items-center rounded-sm border border-border px-1.5 text-xs text-ink-muted">{t("docEditor.noProposal")}</span>}
              <button
                className="rounded-md bg-signal px-3 py-2 text-xs font-semibold text-on-signal hover:brightness-110"
                onClick={saveCurrent}
              >
                Uložit
              </button>
            </div>
          </div>

          <div className="grid gap-3 px-4 py-3">
            <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(180px,1fr))]">
              <RibbonGroup title="Písmo">
                <div className="grid grid-cols-[repeat(auto-fit,minmax(56px,1fr))] gap-2">
                  <RibbonButton onClick={() => editor?.chain().focus().toggleBold().run()}>B</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().toggleItalic().run()}>I</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().toggleUnderline().run()}>U</RibbonButton>
                </div>
                <div className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(72px,1fr))] gap-2">
                  <RibbonButton onClick={() => editor?.chain().focus().setParagraph().run()}>Normální</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}>Nadpis 1</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}>Nadpis 2</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}>Nadpis 3</RibbonButton>
                </div>
              </RibbonGroup>

              <RibbonGroup title="Odstavec">
                <div className="grid grid-cols-[repeat(auto-fit,minmax(56px,1fr))] gap-2">
                  <RibbonButton onClick={() => editor?.chain().focus().setTextAlign("left").run()}>Vlevo</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().setTextAlign("center").run()}>Na střed</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().setTextAlign("right").run()}>Vpravo</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().setTextAlign("justify").run()}>Do bloku</RibbonButton>
                </div>
                <div className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(72px,1fr))] gap-2">
                  <RibbonButton onClick={() => editor?.chain().focus().toggleBulletList().run()}>Odrážky</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().toggleOrderedList().run()}>Číslování</RibbonButton>
                </div>
              </RibbonGroup>

              <RibbonGroup title="Vložit">
                <div className="grid grid-cols-2 gap-2">
                  <RibbonButton
                    onClick={() =>
                      editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
                    }
                  >
                    Tabulka
                  </RibbonButton>
                  <RibbonButton disabled>Obrázek</RibbonButton>
                  <RibbonButton disabled>Zalomení stránky</RibbonButton>
                </div>
                <div className="mt-2 text-[11px] text-ink-muted">(obrázky + DOCX export doplníme)</div>
              </RibbonGroup>

              <RibbonGroup title="Revize">
                <div className="grid grid-cols-2 gap-2">
                  <RibbonButton onClick={() => editor?.chain().focus().undo().run()}>Zpět</RibbonButton>
                  <RibbonButton onClick={() => editor?.chain().focus().redo().run()}>Znovu</RibbonButton>
                </div>
              </RibbonGroup>
            </div>
          </div>
        </div>

        {/* A4 page canvas */}
        <div className="rounded-md border border-border bg-surface-sunken p-6">
          <div className="mx-auto w-full max-w-[820px]">
            <div className="rounded-sm border border-doc-rule bg-doc-paper text-doc-ink">
              <div className="px-16 py-14">
                <div className="max-w-none font-serif">
                  <EditorContent editor={editor} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {hasProposal ? (
          <div className="rounded-md border border-border-strong bg-surface-sunken p-3">
            <div className="text-xs font-semibold text-ink">{t("docEditor.proposalReady")}</div>
            <div className="mt-1 text-xs text-ink-muted">
              {t("docEditor.proposalHelp")}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                className="rounded-md bg-signal px-3 py-2 text-xs font-semibold text-on-signal hover:brightness-110"
                onClick={onAccept}
              >
                {t("docEditor.accept")}
              </button>
              <button
                className="rounded-sm border border-border-strong bg-surface-raised px-3 py-2 text-xs font-semibold text-ink hover:bg-surface-sunken"
                onClick={onReject}
              >
                {t("docEditor.reject")}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <Panel title={t("docEditor.assistant")}>
        <div className="text-xs text-ink-muted">
          {t("docEditor.assistantHelp")}
        </div>

        <label className="mt-3 block text-xs text-ink-muted">
          {t("docEditor.modelRole")}
          <select
            className="mt-1 h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm"
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
          >
            {AGENTS.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-3 block text-xs text-ink-muted">
          {t("docEditor.message")}
          <textarea
            className="mt-1 min-h-[120px] w-full rounded-md border border-border bg-surface-raised p-3 text-sm"
            placeholder={t("docEditor.messagePlaceholder")}
            value={chat}
            onChange={(e) => setChat(e.target.value)}
          />
        </label>

        <div className="mt-3 flex gap-2">
          <button
            className="rounded-md bg-signal px-3 py-2 text-xs font-semibold text-on-signal hover:brightness-110"
            onClick={generateProposal}
          >
            {t("docEditor.generate")}
          </button>
        </div>

        {state.lastProposalMeta ? (
          <div className="mt-4 rounded-md border border-border bg-surface-raised p-3">
            <div className="text-xs font-semibold text-ink">{t("docEditor.lastProposal")}</div>
            <div className="mt-1 text-xs text-ink-muted">
              {t("docEditor.modelRole")}: <span className="font-medium">{state.lastProposalMeta.agent}</span>
              <br />
              {t("docEditor.time")}: {new Date(state.lastProposalMeta.createdAt).toLocaleString("cs-CZ")}
            </div>
            <div className="mt-2 text-xs text-ink-muted">{t("docEditor.message")}: {state.lastProposalMeta.prompt}</div>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
