"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";

import { type DeckEvaluation, evaluateDeckUpload } from "@/lib/api";

type UploadState =
  | { status: "idle" }
  | { status: "success"; payload: DeckEvaluation }
  | { status: "error"; message: string };

export function DeckUploadWidget() {
  const router = useRouter();
  const [selectedPdf, setSelectedPdf] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle" });
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isPending, startTransition] = useTransition();

  function setPdfFromList(fileList: FileList | null) {
    const file = fileList?.[0] ?? null;
    if (!file) return;
    setSelectedPdf(file);
    setUploadState({ status: "idle" });
  }

  return (
    <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Insert Another Deck</p>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Upload and evaluate a new PDF</h2>
        <p className="max-w-2xl text-sm leading-7 text-slate-600">
          Drop a pitch deck PDF here and the backend will store it, evaluate it, and add it to the gallery.
        </p>
      </div>

      <form
        action={(formData) => {
          startTransition(async () => {
            const evalFlag = String(formData.get("eval") ?? "true") === "true";
            if (!selectedPdf) {
              setUploadState({ status: "error", message: "Select or drop a PDF file." });
              return;
            }

            try {
              const payload = await evaluateDeckUpload(selectedPdf, evalFlag);
              setUploadState({ status: "success", payload });
              setSelectedPdf(null);
              if (fileInputRef.current) fileInputRef.current.value = "";
              router.refresh();
            } catch (error) {
              setUploadState({ status: "error", message: error instanceof Error ? error.message : "Request failed." });
            }
          });
        }}
        className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]"
      >
        <div className="space-y-4">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => setPdfFromList(event.target.files)}
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
              setIsDragging(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setIsDragging(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              setPdfFromList(event.dataTransfer.files);
            }}
            className={`rounded-[1.5rem] border border-dashed px-6 py-12 text-left transition ${
              isDragging
                ? "border-slate-900 bg-slate-100"
                : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-white"
            }`}
          >
            <p className="text-base font-medium text-slate-950">
              {selectedPdf ? selectedPdf.name : "Drop a PDF here or click to choose a file"}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              {selectedPdf
                ? `${Math.max(1, Math.round(selectedPdf.size / 1024))} KB selected`
                : "PDF only. The file will be uploaded to Supabase Storage, then evaluated and ingested."}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-4 rounded-[1.5rem] bg-slate-950 p-5 text-white">
          <label className="text-sm font-medium text-slate-200" htmlFor="eval-mode">
            Processing mode
          </label>
          <select
            id="eval-mode"
            name="eval"
            defaultValue="true"
            className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-slate-400"
          >
            <option value="true">Full evaluation</option>
            <option value="false">Deck extraction only</option>
          </select>

          <button
            type="submit"
            disabled={isPending}
            className="mt-auto rounded-xl bg-white px-4 py-3 text-sm font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "Uploading..." : "Insert deck"}
          </button>
        </div>
      </form>

      {uploadState.status === "error" ? (
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{uploadState.message}</div>
      ) : null}

      {uploadState.status === "success" ? (
        <div className="mt-5 rounded-[1.5rem] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <p className="font-medium">Deck ingested successfully.</p>
          <p className="mt-1">
            {uploadState.payload.deck?.company ?? "Untitled deck"} was evaluated and added to the gallery.
          </p>
        </div>
      ) : null}
    </section>
  );
}
