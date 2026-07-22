"use client";

import { useRef, useState, useTransition } from "react";

import {
  type Deck,
  type DeckEvaluation,
  evaluateDeckUpload,
  ingestDeckFromJson,
  loadDeckFromJson,
  retrieveDeck,
} from "@/lib/api";

type ActionState =
  | { status: "idle" }
  | { status: "success"; payload: unknown }
  | { status: "error"; message: string };

function ResultBlock({ state }: { state: ActionState }) {
  if (state.status === "idle") return null;

  if (state.status === "error") {
    return <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{state.message}</div>;
  }

  return (
    <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-6 text-slate-100">
      {JSON.stringify(state.payload, null, 2)}
    </pre>
  );
}

function WorkflowCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-sm text-slate-600">{description}</p>
      </div>
      {children}
    </section>
  );
}

export function DeckWorkflows() {
  const [loadState, setLoadState] = useState<ActionState>({ status: "idle" });
  const [ingestState, setIngestState] = useState<ActionState>({ status: "idle" });
  const [retrieveState, setRetrieveState] = useState<ActionState>({ status: "idle" });
  const [evaluateState, setEvaluateState] = useState<ActionState>({ status: "idle" });
  const [selectedPdf, setSelectedPdf] = useState<File | null>(null);
  const [isDraggingPdf, setIsDraggingPdf] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [loadPending, startLoad] = useTransition();
  const [ingestPending, startIngest] = useTransition();
  const [retrievePending, startRetrieve] = useTransition();
  const [evaluatePending, startEvaluate] = useTransition();

  async function handleJsonAction(
    formData: FormData,
    setter: (value: ActionState) => void,
    action: (jsonPath: string) => Promise<Deck | { deck_id: string; status: string; company: string }>
  ) {
    const jsonPath = String(formData.get("json_path") ?? "").trim();
    if (!jsonPath) {
      setter({ status: "error", message: "A JSON path is required." });
      return;
    }

    try {
      const payload = await action(jsonPath);
      setter({ status: "success", payload });
    } catch (error) {
      setter({ status: "error", message: error instanceof Error ? error.message : "Request failed." });
    }
  }

  function setPdfFromList(fileList: FileList | null) {
    const file = fileList?.[0] ?? null;
    if (!file) return;
    setSelectedPdf(file);
    setEvaluateState({ status: "idle" });
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <WorkflowCard title="Upload / Load JSON Deck" description="Call /api/decks/from-json and inspect the parsed deck metadata and slides.">
        <form
          action={(formData) => {
            startLoad(() => void handleJsonAction(formData, setLoadState, loadDeckFromJson));
          }}
          className="space-y-4"
        >
          <input
            name="json_path"
            placeholder="/absolute/path/to/deck.json"
            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-900"
          />
          <button
            type="submit"
            disabled={loadPending}
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loadPending ? "Loading..." : "Load deck"}
          </button>
        </form>
        <div className="mt-4">
          <ResultBlock state={loadState} />
        </div>
      </WorkflowCard>

      <WorkflowCard title="Ingest Deck Into Database" description="Call /api/decks/ingest-from-json and capture the returned deck_id.">
        <form
          action={(formData) => {
            startIngest(() => void handleJsonAction(formData, setIngestState, ingestDeckFromJson));
          }}
          className="space-y-4"
        >
          <input
            name="json_path"
            placeholder="/absolute/path/to/deck.json"
            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-900"
          />
          <button
            type="submit"
            disabled={ingestPending}
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {ingestPending ? "Ingesting..." : "Ingest deck"}
          </button>
        </form>
        <div className="mt-4">
          <ResultBlock state={ingestState} />
        </div>
      </WorkflowCard>

      <WorkflowCard title="Retrieve Deck" description="Call /api/decks/retrieve with a deck_id and show the deck plus slides.">
        <form
          action={(formData) => {
            startRetrieve(async () => {
              const deckId = String(formData.get("deck_id") ?? "").trim();
              if (!deckId) {
                setRetrieveState({ status: "error", message: "A deck_id is required." });
                return;
              }
              try {
                const payload = await retrieveDeck(deckId);
                setRetrieveState({ status: "success", payload });
              } catch (error) {
                setRetrieveState({ status: "error", message: error instanceof Error ? error.message : "Request failed." });
              }
            });
          }}
          className="space-y-4"
        >
          <input
            name="deck_id"
            placeholder="deck_id"
            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-900"
          />
          <button
            type="submit"
            disabled={retrievePending}
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {retrievePending ? "Retrieving..." : "Retrieve deck"}
          </button>
        </form>
        <div className="mt-4">
          <ResultBlock state={retrieveState} />
        </div>
      </WorkflowCard>

      <WorkflowCard title="Evaluate Deck" description="Upload a PDF and call the backend evaluation endpoint to render scores, red flags, and summary output.">
        <form
          action={(formData) => {
            startEvaluate(async () => {
              const evalFlag = String(formData.get("eval") ?? "true") === "true";
              const visibleToVcs = formData.get("visible_to_vcs") === "on";
              if (!selectedPdf) {
                setEvaluateState({ status: "error", message: "Select or drop a PDF file." });
                return;
              }
              try {
                const payload: DeckEvaluation = await evaluateDeckUpload(selectedPdf, evalFlag, visibleToVcs);
                setEvaluateState({ status: "success", payload });
              } catch (error) {
                setEvaluateState({ status: "error", message: error instanceof Error ? error.message : "Request failed." });
              }
            });
          }}
          className="space-y-4"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => {
              setPdfFromList(event.target.files);
            }}
          />
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDraggingPdf(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setIsDraggingPdf(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setIsDraggingPdf(false);
              setPdfFromList(event.dataTransfer.files);
            }}
            className={`rounded-2xl border border-dashed px-5 py-8 text-left transition ${
              isDraggingPdf
                ? "border-slate-900 bg-slate-100"
                : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-white"
            }`}
          >
            <p className="text-sm font-medium text-slate-900">
              {selectedPdf ? selectedPdf.name : "Drop a PDF here or click to choose a file"}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {selectedPdf
                ? `${Math.max(1, Math.round(selectedPdf.size / 1024))} KB selected`
                : "The file is uploaded directly to the backend for evaluation."}
            </p>
          </div>
          <select
            name="eval"
            defaultValue="true"
            className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900"
          >
            <option value="true">Full evaluation</option>
            <option value="false">Deck extraction only</option>
          </select>
          <label className="flex items-center gap-3 rounded-xl border border-slate-300 px-4 py-3 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              name="visible_to_vcs"
              className="h-4 w-4 accent-slate-900"
            />
            Make this deck visible to VC profiles
          </label>
          <button
            type="submit"
            disabled={evaluatePending}
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {evaluatePending ? "Evaluating..." : "Evaluate deck"}
          </button>
        </form>
        <div className="mt-4">
          <ResultBlock state={evaluateState} />
        </div>
      </WorkflowCard>
    </div>
  );
}
