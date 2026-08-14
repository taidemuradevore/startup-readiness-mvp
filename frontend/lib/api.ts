export type DeckSlide = {
  slide_number: number;
  text: string;
  graph_desc: string[];
  section: string;
};

export type Deck = {
  deck_id?: string;
  title: string;
  company: string;
  company_name?: string;
  team: string[];
  stage: string;
  sector: string;
  slides?: DeckSlide[];
};

export type DeckSummary = {
  deck_id: string;
  company_name: string;
  sector: string;
  stage: string;
  team: string[];
  storage_object_path?: string | null;
  deck_pdf_url?: string | null;
  visible_to_vcs?: boolean;
  can_manage_visibility?: boolean;
  match_score?: number | null;
  match_reason?: string | null;
  matched_facets?: Array<{
    facet_type: string;
    facet_title: string;
    score: number;
  }>;
  score_summary?: {
    overall_score: number | null;
    raw_overall_score?: number | null;
    confidence_adjusted_overall_score?: number | null;
    scored_sections: number;
    red_flag_count: number;
    red_flags: string[];
    score_breakdown: Array<{
      rubric_section: string;
      value: number | null;
      raw_score?: string | null;
      feedback?: string | null;
      evidence?: string | null;
      confidence?: number | null;
      adjusted_value?: number | null;
      confidence_reason?: string | null;
      verification_status?: string | null;
      critic_notes?: string | null;
      external_checks?: ExternalCheckResult[];
    }>;
  } | null;
};

export type ExternalCheckResult = {
  claim: string;
  source: string;
  status: "verified" | "unverified" | "contradicted" | "unavailable";
  summary: string;
  url?: string | null;
};

export type DeckEvaluationSection = {
  is_present: boolean;
  score: number | string | null;
  feedback: string | null;
  evidence: string | null;
  confidence?: number | null;
  adjusted_score?: number | null;
  confidence_reason?: string | null;
  verification_status?: string | null;
  critic_notes?: string | null;
  external_checks?: ExternalCheckResult[];
};

export type DeckEvaluation = {
  deck: Deck | null;
  extracted_kpis: Array<{ kpi_name: string; kpi_value: string; provenance?: string | null }>;
  red_flags: string[];
  final_grade?: string | null;
  s1_problem: DeckEvaluationSection;
  s2_solution: DeckEvaluationSection;
  s3_market_size: DeckEvaluationSection;
  s4_product_and_tech: DeckEvaluationSection;
  s5_business_model: DeckEvaluationSection;
  s6_go_to_market: DeckEvaluationSection;
  s7_competition: DeckEvaluationSection;
  s8_team: DeckEvaluationSection;
  s9_traction_and_kpis: DeckEvaluationSection;
  s10_the_ask_and_financials: DeckEvaluationSection;
};

export type ProfileType = "startup" | "vc";

export type UserProfile = {
  user_id: string;
  profile_type: ProfileType;
  organization_name: string;
  website: string;
  role_title: string;
  sector_focus: string;
  geography: string;
  description: string;
  startup_stage: string | null;
  fund_stage_focus: string | null;
  check_size_range: string | null;
  fundraising_status: string | null;
  target_raise: string | null;
  traction_summary: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ProfilePayload = {
  profile_type: ProfileType;
  organization_name: string;
  website: string;
  role_title: string;
  sector_focus: string;
  geography: string;
  description: string;
  startup_stage?: string | null;
  fund_stage_focus?: string | null;
  check_size_range?: string | null;
  fundraising_status?: string | null;
  target_raise?: string | null;
  traction_summary?: string | null;
  notes?: string | null;
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const ENABLE_EXAMPLE_DECKS = process.env.NEXT_PUBLIC_ENABLE_EXAMPLE_DECKS === "true";

type RequestOptions = {
  accessToken?: string | null;
};

function isSupabaseConfigured() {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL &&
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  );
}

async function getBrowserSupabaseAccessToken() {
  if (!isSupabaseConfigured() || typeof window === "undefined") {
    return null;
  }

  const { createClient } = await import("@/lib/supabase/client");
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

const fallbackDecks: DeckSummary[] = [
  {
    deck_id: "fallback-acme-ai",
    company_name: "Acme AI",
    sector: "AI Infrastructure",
    stage: "Seed",
    team: ["Maya Chen", "Drew Patel"],
    deck_pdf_url: null,
    score_summary: {
      overall_score: 82.5,
      scored_sections: 10,
      red_flag_count: 1,
      red_flags: ["Differentiation against incumbent workflow platforms is implied more than proven."],
      score_breakdown: [
        { rubric_section: "Problem", value: 17.0 },
        {
          rubric_section: "Solution",
          value: 16.0,
          feedback: "Product positioning is clear, but the deck could sharpen why incumbents cannot copy the workflow layer.",
          evidence: "\"Unified orchestration, evaluation, and observability layer\"",
        },
      ],
    },
  },
  {
    deck_id: "fallback-nimbus-health",
    company_name: "Nimbus Health",
    sector: "Digital Health",
    stage: "Series A",
    team: ["Lena Brooks", "Omar Rahman", "Tina Park"],
    deck_pdf_url: null,
    score_summary: {
      overall_score: 74.0,
      scored_sections: 9,
      red_flag_count: 2,
      red_flags: [
        "Go-to-market ownership is not tied tightly enough to the milestones in the raise.",
        "Financial planning detail is thinner than expected for this stage.",
      ],
      score_breakdown: [
        { rubric_section: "Market Size", value: 8.0 },
        {
          rubric_section: "Team",
          value: 8.5,
          feedback: "The team story is credible and operator-heavy, but execution roles could be tied more directly to go-to-market milestones.",
        },
      ],
    },
  },
];

const fallbackSlides: Record<string, DeckSlide[]> = {
  "fallback-acme-ai": [
    {
      slide_number: 1,
      section: "Problem",
      text: "Teams cannot productionize AI workflows quickly because model orchestration and eval pipelines are fragmented.",
      graph_desc: ["Title slide with company name and product positioning."],
    },
    {
      slide_number: 2,
      section: "Solution",
      text: "Acme AI provides a unified orchestration, evaluation, and observability layer for enterprise AI systems.",
      graph_desc: ["Architecture diagram showing data, models, evals, and monitoring."],
    },
  ],
  "fallback-nimbus-health": [
    {
      slide_number: 1,
      section: "Problem",
      text: "Specialty clinics struggle with high no-show rates and fragmented patient communication.",
      graph_desc: ["Chart comparing clinic utilization rates before and after intervention."],
    },
    {
      slide_number: 2,
      section: "Team",
      text: "Founding team includes former operators from Epic, Oscar, and a previous healthtech exit.",
      graph_desc: ["Team slide with prior companies and roles."],
    },
  ],
};

class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit, options: RequestOptions = {}): Promise<T> {
  if (!API_URL) {
    throw new ApiError("NEXT_PUBLIC_API_URL is not configured.");
  }

  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const accessToken = options.accessToken ?? (await getBrowserSupabaseAccessToken());

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail || `Request failed for ${path}`, response.status);
  }

  return (await response.json()) as T;
}

function normalizeDeckSummary(deck: Partial<Deck> & { deck_id?: string }): DeckSummary {
  return {
    deck_id:
      deck.deck_id ??
      deck.company?.toLowerCase().replace(/[^a-z0-9]+/g, "-") ??
      deck.title?.toLowerCase().replace(/[^a-z0-9]+/g, "-") ??
      "unknown-deck",
    company_name: deck.company_name ?? deck.company ?? deck.title ?? "Untitled Deck",
    sector: deck.sector ?? "Unknown",
    stage: deck.stage ?? "Unknown",
    team: deck.team ?? [],
    storage_object_path: "storage_object_path" in deck ? (deck as DeckSummary).storage_object_path : null,
    deck_pdf_url: "deck_pdf_url" in deck ? (deck as DeckSummary).deck_pdf_url : null,
    visible_to_vcs: "visible_to_vcs" in deck ? (deck as DeckSummary).visible_to_vcs : false,
    can_manage_visibility: "can_manage_visibility" in deck ? (deck as DeckSummary).can_manage_visibility : false,
    match_score: "match_score" in deck ? (deck as DeckSummary).match_score : null,
    match_reason: "match_reason" in deck ? (deck as DeckSummary).match_reason : null,
    matched_facets: "matched_facets" in deck ? (deck as DeckSummary).matched_facets : [],
    score_summary: "score_summary" in deck ? (deck as DeckSummary).score_summary : null,
  };
}

export async function getDecks(options: RequestOptions = {}): Promise<{ decks: DeckSummary[]; isFallback: boolean; error?: string }> {
  if (!API_URL) {
    return {
      decks: ENABLE_EXAMPLE_DECKS ? fallbackDecks : [],
      isFallback: true,
      error: "NEXT_PUBLIC_API_URL is not configured.",
    };
  }

  try {
    const data = await request<DeckSummary[] | { decks: DeckSummary[] }>("/api/decks", undefined, options);
    return { decks: Array.isArray(data) ? data : data.decks, isFallback: false };
  } catch (error) {
    return {
      decks: ENABLE_EXAMPLE_DECKS ? fallbackDecks : [],
      isFallback: true,
      error: error instanceof Error ? error.message : "Deck list request failed.",
    };
  }
}

export async function getUserProfile(options: RequestOptions = {}): Promise<UserProfile | null> {
  return request<UserProfile | null>("/api/profile", undefined, options);
}

export async function saveUserProfile(payload: ProfilePayload): Promise<UserProfile> {
  return request<UserProfile>("/api/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getDeckSlides(deckId: string, options: RequestOptions = {}): Promise<{ slides: DeckSlide[]; isFallback: boolean }> {
  if (!API_URL) {
    return { slides: ENABLE_EXAMPLE_DECKS ? fallbackSlides[deckId] ?? [] : [], isFallback: true };
  }

  try {
    const data = await request<DeckSlide[] | { slides: DeckSlide[] }>(`/api/decks/${deckId}/slides`, undefined, options);
    return { slides: Array.isArray(data) ? data : data.slides, isFallback: false };
  } catch {
    return { slides: ENABLE_EXAMPLE_DECKS ? fallbackSlides[deckId] ?? [] : [], isFallback: true };
  }
}

export async function getDeckMetadata(deckId: string, options: RequestOptions = {}): Promise<DeckSummary> {
  return request<DeckSummary>(`/api/decks/${deckId}`, undefined, options);
}

export async function deleteDeck(deckId: string): Promise<{ status: string; deck_id: string }> {
  return request<{ status: string; deck_id: string }>(`/api/decks/${deckId}`, {
    method: "DELETE",
  });
}

export async function retrieveDeck(deckId: string): Promise<Deck> {
  return request<Deck>("/api/decks/retrieve", {
    method: "POST",
    body: JSON.stringify({ deck_id: deckId }),
  });
}

export async function loadDeckFromJson(jsonPath: string): Promise<Deck> {
  return request<Deck>("/api/decks/from-json", {
    method: "POST",
    body: JSON.stringify({ json_path: jsonPath }),
  });
}

export async function ingestDeckFromJson(jsonPath: string): Promise<{ status: string; deck_id: string; company: string }> {
  return request<{ status: string; deck_id: string; company: string }>("/api/decks/ingest-from-json", {
    method: "POST",
    body: JSON.stringify({ json_path: jsonPath }),
  });
}

export async function evaluateDeck(pdfPath: string, evalFlag: boolean): Promise<DeckEvaluation> {
  return request<DeckEvaluation>("/api/decks/evaluate", {
    method: "POST",
    body: JSON.stringify({ pdf_path: pdfPath, eval: evalFlag }),
  });
}

export async function evaluateDeckUpload(file: File, evalFlag: boolean, visibleToVcs: boolean): Promise<DeckEvaluation> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("eval", String(evalFlag));
  formData.append("visible_to_vcs", String(visibleToVcs));

  return request<DeckEvaluation>("/api/decks/evaluate-upload", {
    method: "POST",
    body: formData,
  });
}

export async function updateDeckVisibility(deckId: string, visibleToVcs: boolean): Promise<{
  deck_id: string;
  visible_to_vcs: boolean;
  can_manage_visibility: boolean;
}> {
  return request<{
    deck_id: string;
    visible_to_vcs: boolean;
    can_manage_visibility: boolean;
  }>(`/api/decks/${deckId}/visibility`, {
    method: "PATCH",
    body: JSON.stringify({ visible_to_vcs: visibleToVcs }),
  });
}

export async function getDeckDetail(deckId: string, options: RequestOptions = {}): Promise<{ deck: DeckSummary; slides: DeckSlide[]; isFallback: boolean }> {
  const slidesResult = await getDeckSlides(deckId, options);

  try {
    const retrieved = await getDeckMetadata(deckId, options);
    return {
      deck: normalizeDeckSummary({ ...retrieved, deck_id: deckId }),
      slides: slidesResult.slides,
      isFallback: slidesResult.isFallback,
    };
  } catch {
    const fallbackDeck = ENABLE_EXAMPLE_DECKS ? fallbackDecks.find((item) => item.deck_id === deckId) : undefined;
    if (!fallbackDeck && !slidesResult.slides.length) {
      throw new ApiError(`Deck ${deckId} could not be loaded.`);
    }
    return {
      deck:
        fallbackDeck ??
        normalizeDeckSummary({
          deck_id: deckId,
          title: deckId,
          company: deckId,
          sector: "Unknown",
          stage: "Unknown",
          team: [],
        }),
      slides: slidesResult.slides,
      isFallback: true,
    };
  }
}
