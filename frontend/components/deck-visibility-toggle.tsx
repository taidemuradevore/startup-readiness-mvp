"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { updateDeckVisibility } from "@/lib/api";

export function DeckVisibilityToggle({
  deckId,
  initialVisible,
  className = "",
}: {
  deckId: string;
  initialVisible: boolean;
  className?: string;
}) {
  const router = useRouter();
  const [isVisible, setIsVisible] = useState(initialVisible);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => {
          const nextVisible = !isVisible;
          startTransition(async () => {
            setError(null);
            try {
              const result = await updateDeckVisibility(deckId, nextVisible);
              setIsVisible(result.visible_to_vcs);
              router.refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Visibility update failed.");
            }
          });
        }}
        disabled={isPending}
        className={`rounded-xl border px-4 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
          isVisible
            ? "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
        } ${className}`}
      >
        {isPending ? "Updating..." : isVisible ? "Visible to VCs" : "Hidden from VCs"}
      </button>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
    </div>
  );
}
