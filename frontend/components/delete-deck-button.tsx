"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { deleteDeck } from "@/lib/api";

export function DeleteDeckButton({
  deckId,
  redirectToHome = false,
  className = "",
}: {
  deckId: string;
  redirectToHome?: boolean;
  className?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => {
          const confirmed = window.confirm("Delete this deck and its stored PDF?");
          if (!confirmed) return;

          startTransition(async () => {
            setError(null);
            try {
              await deleteDeck(deckId);
              if (redirectToHome) {
                router.push("/");
                router.refresh();
                return;
              }
              router.refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Delete failed.");
            }
          });
        }}
        disabled={isPending}
        className={`rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      >
        {isPending ? "Deleting..." : "Delete deck"}
      </button>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
    </div>
  );
}
