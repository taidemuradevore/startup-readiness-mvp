"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";

import { type ProfilePayload, type ProfileType, type UserProfile, saveUserProfile } from "@/lib/api";

type ProfileModalProps = {
  initialProfile: UserProfile | null;
  autoOpen: boolean;
  className?: string;
};

type ProfileFormState = {
  profile_type: ProfileType;
  organization_name: string;
  website: string;
  role_title: string;
  sector_focus: string;
  geography: string;
  description: string;
  startup_stage: string;
  fund_stage_focus: string;
  check_size_range: string;
  fundraising_status: string;
  target_raise: string;
  traction_summary: string;
  notes: string;
};

type SaveState =
  | { status: "idle" }
  | { status: "success" }
  | { status: "error"; message: string };

const DISMISSED_KEY = "startup-readiness-profile-dismissed";

function profileToForm(profile: UserProfile | null): ProfileFormState {
  return {
    profile_type: profile?.profile_type ?? "startup",
    organization_name: profile?.organization_name ?? "",
    website: profile?.website ?? "",
    role_title: profile?.role_title ?? "",
    sector_focus: profile?.sector_focus ?? "",
    geography: profile?.geography ?? "",
    description: profile?.description ?? "",
    startup_stage: profile?.startup_stage ?? "",
    fund_stage_focus: profile?.fund_stage_focus ?? "",
    check_size_range: profile?.check_size_range ?? "",
    fundraising_status: profile?.fundraising_status ?? "",
    target_raise: profile?.target_raise ?? "",
    traction_summary: profile?.traction_summary ?? "",
    notes: profile?.notes ?? "",
  };
}

function cleanOptional(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function TextField({
  label,
  value,
  onChange,
  required = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        placeholder={placeholder}
        className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-500"
      />
    </label>
  );
}

function TextAreaField({
  label,
  value,
  onChange,
  required = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        rows={4}
        placeholder={placeholder}
        className="mt-2 w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-6 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-500"
      />
    </label>
  );
}

export function ProfileModal({ initialProfile, autoOpen, className = "" }: ProfileModalProps) {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(initialProfile);
  const [isOpen, setIsOpen] = useState(false);
  const [formState, setFormState] = useState<ProfileFormState>(() => profileToForm(initialProfile));
  const [saveState, setSaveState] = useState<SaveState>({ status: "idle" });
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!autoOpen || profile) return;
    const wasDismissed = window.sessionStorage.getItem(DISMISSED_KEY) === "true";
    if (!wasDismissed) {
      const timer = window.setTimeout(() => setIsOpen(true), 0);
      return () => window.clearTimeout(timer);
    }
  }, [autoOpen, profile]);

  const titleCopy = useMemo(() => {
    if (formState.profile_type === "vc") {
      return {
        heading: "Investor profile",
        organization: "Firm name",
        description: "Investment thesis",
      };
    }

    return {
      heading: "Startup profile",
      organization: "Company name",
      description: "Company description",
    };
  }, [formState.profile_type]);

  function updateField<Field extends keyof ProfileFormState>(field: Field, value: ProfileFormState[Field]) {
    setFormState((current) => ({ ...current, [field]: value }));
    setSaveState({ status: "idle" });
  }

  function closeModal() {
    if (!profile) {
      window.sessionStorage.setItem(DISMISSED_KEY, "true");
    }
    setIsOpen(false);
  }

  function buildPayload(): ProfilePayload {
    return {
      profile_type: formState.profile_type,
      organization_name: formState.organization_name.trim(),
      website: formState.website.trim(),
      role_title: formState.role_title.trim(),
      sector_focus: formState.sector_focus.trim(),
      geography: formState.geography.trim(),
      description: formState.description.trim(),
      startup_stage: formState.profile_type === "startup" ? formState.startup_stage.trim() : null,
      fund_stage_focus: formState.profile_type === "vc" ? formState.fund_stage_focus.trim() : null,
      check_size_range: cleanOptional(formState.check_size_range),
      fundraising_status: formState.profile_type === "startup" ? cleanOptional(formState.fundraising_status) : null,
      target_raise: formState.profile_type === "startup" ? cleanOptional(formState.target_raise) : null,
      traction_summary: formState.profile_type === "startup" ? cleanOptional(formState.traction_summary) : null,
      notes: cleanOptional(formState.notes),
    };
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={`rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 ${className}`}
      >
        Profile
      </button>

      {isOpen && typeof document !== "undefined" ? createPortal(
        <div
          className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 px-4 py-4 sm:py-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="profile-modal-title"
        >
          <div className="mx-auto flex min-h-0 w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl sm:max-h-[calc(100vh-3rem)]">
            <form
              className="flex min-h-0 flex-1 flex-col"
              action={() => {
                startTransition(async () => {
                  try {
                    const savedProfile = await saveUserProfile(buildPayload());
                    setProfile(savedProfile);
                    setFormState(profileToForm(savedProfile));
                    window.sessionStorage.removeItem(DISMISSED_KEY);
                    setSaveState({ status: "success" });
                    setIsOpen(false);
                    router.refresh();
                  } catch (error) {
                    setSaveState({
                      status: "error",
                      message: error instanceof Error ? error.message : "Profile could not be saved.",
                    });
                  }
                });
              }}
            >
              <div className="border-b border-slate-200 px-6 py-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Account Profile</p>
                    <h2 id="profile-modal-title" className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                      {profile ? "Edit your profile" : "Complete your profile"}
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={closeModal}
                    className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
                  >
                    Close
                  </button>
                </div>
              </div>

              <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-6">
                <fieldset>
                  <legend className="text-sm font-medium text-slate-700">Profile type</legend>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    {(["startup", "vc"] as const).map((type) => (
                      <label
                        key={type}
                        className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium transition ${
                          formState.profile_type === type
                            ? "border-slate-950 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        <input
                          type="radio"
                          name="profile_type"
                          value={type}
                          checked={formState.profile_type === type}
                          onChange={() => updateField("profile_type", type)}
                          className="h-4 w-4 accent-slate-950"
                        />
                        {type === "startup" ? "Startup" : "VC / Investor"}
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="grid gap-4 md:grid-cols-2">
                  <TextField
                    label={titleCopy.organization}
                    value={formState.organization_name}
                    onChange={(value) => updateField("organization_name", value)}
                    required
                    placeholder={formState.profile_type === "startup" ? "Acme AI" : "Northstar Ventures"}
                  />
                  <TextField
                    label="Website"
                    value={formState.website}
                    onChange={(value) => updateField("website", value)}
                    required
                    placeholder="https://example.com"
                  />
                  <TextField
                    label="Your role/title"
                    value={formState.role_title}
                    onChange={(value) => updateField("role_title", value)}
                    required
                    placeholder={formState.profile_type === "startup" ? "Founder / CEO" : "Partner"}
                  />
                  {formState.profile_type === "startup" ? (
                    <TextField
                      label="Startup stage"
                      value={formState.startup_stage}
                      onChange={(value) => updateField("startup_stage", value)}
                      required
                      placeholder="Pre-seed, Seed, Series A"
                    />
                  ) : (
                    <TextField
                      label="Fund stage focus"
                      value={formState.fund_stage_focus}
                      onChange={(value) => updateField("fund_stage_focus", value)}
                      required
                      placeholder="Pre-seed through Series A"
                    />
                  )}
                  <TextField
                    label="Sector/focus"
                    value={formState.sector_focus}
                    onChange={(value) => updateField("sector_focus", value)}
                    required
                    placeholder="AI infrastructure, healthcare, fintech"
                  />
                  <TextField
                    label="Geography"
                    value={formState.geography}
                    onChange={(value) => updateField("geography", value)}
                    required
                    placeholder="United States, Europe, Global"
                  />
                </div>

                <TextAreaField
                  label={titleCopy.description}
                  value={formState.description}
                  onChange={(value) => updateField("description", value)}
                  required
                  placeholder={formState.profile_type === "startup" ? "What you build, who it serves, and why now." : "What you invest in and how you evaluate opportunities."}
                />

                <div>
                  <h3 className="text-sm font-semibold text-slate-950">{titleCopy.heading} details</h3>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <TextField
                      label="Check size range"
                      value={formState.check_size_range}
                      onChange={(value) => updateField("check_size_range", value)}
                      placeholder={formState.profile_type === "startup" ? "$500k-$2M target investors" : "$250k-$1.5M"}
                    />
                    {formState.profile_type === "startup" ? (
                      <>
                        <TextField
                          label="Fundraising status"
                          value={formState.fundraising_status}
                          onChange={(value) => updateField("fundraising_status", value)}
                          placeholder="Raising now, preparing, not raising"
                        />
                        <TextField
                          label="Target raise"
                          value={formState.target_raise}
                          onChange={(value) => updateField("target_raise", value)}
                          placeholder="$1.5M seed"
                        />
                        <TextAreaField
                          label="Traction summary"
                          value={formState.traction_summary}
                          onChange={(value) => updateField("traction_summary", value)}
                          placeholder="Revenue, pilots, users, growth, or proof points."
                        />
                      </>
                    ) : null}
                    <TextAreaField
                      label="Notes"
                      value={formState.notes}
                      onChange={(value) => updateField("notes", value)}
                      placeholder="Anything else useful for deck review context."
                    />
                  </div>
                </div>

                {saveState.status === "error" ? (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {saveState.message}
                  </div>
                ) : null}

                {saveState.status === "success" ? (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    Profile saved.
                  </div>
                ) : null}
              </div>

              <div className="flex flex-col-reverse gap-3 border-t border-slate-200 px-6 py-5 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  Remind me later
                </button>
                <button
                  type="submit"
                  disabled={isPending}
                  className="rounded-xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isPending ? "Saving..." : "Save profile"}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body,
      ) : null}
    </>
  );
}
