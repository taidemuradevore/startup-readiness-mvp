import json
import hashlib
import os
import re
import unittest
from typing import Callable

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from supabase import Client
try:
    from .llm_parser import Deck, DeckSlide, PitchDeckEvaluation
except ImportError:
    from llm_parser import Deck, DeckSlide, PitchDeckEvaluation

load_dotenv()

class SQLDatabase():
    def __init__(self) -> None:
        pass

    def connect(self):
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is not set in the environment")
        return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)

    def load_deck_from_json(self, json_path: str) -> Deck:
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Deck JSON file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        slides = [
            DeckSlide(
                slide_number=slide["slide_number"],
                text=slide.get("text", ""),
                graph_desc=slide.get("graph_desc", []),
                section=slide.get("section", ""),
            )
            for slide in payload.get("slides", [])
        ]

        return Deck(
            title=payload.get("title", payload.get("company", "")),
            company=payload.get("company", ""),
            team=payload.get("team", []),
            stage=payload.get("stage", ""),
            sector=payload.get("sector", ""),
            slides=slides,
        )

    def _make_deck_id(self, deck: Deck, owner_id: str | None = None):
        base = deck.company if deck.company else deck.title
        base_id = "".join(ch.lower() if ch.isalnum() else "_" for ch in base).strip("_") or "deck"
        if not owner_id:
            return base_id
        owner_suffix = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:8]
        return f"{base_id}_{owner_suffix}"

    def _normalize_score_value(self, rubric_section: str, raw_score):
        if raw_score is None:
            return None

        if isinstance(raw_score, (int, float)):
            return float(raw_score)

        if not isinstance(raw_score, str):
            return None

        score_text = raw_score.strip()
        if not score_text:
            return None

        numeric_match = re.search(r"-?\d+(?:\.\d+)?", score_text)
        if numeric_match:
            return float(numeric_match.group(0))

        normalized = score_text.lower()

        if rubric_section == "The Ask & Financials":
            ask_band_map = {
                "clear": 5.0,
                "present": 3.0,
                "adequate": 3.0,
                "absent": 1.0,
                "poor": 1.0,
                "n/a": None,
            }
            for label, value in ask_band_map.items():
                if label in normalized:
                    return value

        band_map = {
            "Problem": {
                "exceptional": 18.5,
                "strong": 14.5,
                "adequate": 10.5,
                "weak": 6.5,
                "poor": 2.5,
            },
            "Solution": {
                "exceptional": 18.5,
                "strong": 14.5,
                "adequate": 10.5,
                "weak": 6.5,
                "poor": 2.5,
            },
            "Market Size": {
                "exceptional": 9.5,
                "strong": 7.5,
                "adequate": 5.5,
                "weak": 3.5,
                "poor": 1.5,
            },
            "Product & Tech": {
                "exceptional": 5.0,
                "strong": 4.0,
                "adequate": 3.0,
                "weak": 2.0,
                "poor": 1.0,
            },
            "Business Model": {
                "exceptional": 9.5,
                "strong": 7.5,
                "adequate": 5.5,
                "weak": 3.5,
                "poor": 1.5,
            },
            "Go-To-Market": {
                "exceptional": 9.5,
                "strong": 7.5,
                "adequate": 5.5,
                "weak": 3.5,
                "poor": 1.5,
            },
            "Competition": {
                "exceptional": 5.0,
                "strong": 4.0,
                "adequate": 3.0,
                "weak": 2.0,
                "poor": 1.0,
            },
            "Team": {
                "exceptional": 18.5,
                "strong": 14.5,
                "adequate": 10.5,
                "weak": 6.5,
                "poor": 2.5,
            },
            "Traction & KPIs": {
                "exceptional": 5.0,
                "strong": 4.0,
                "adequate": 3.0,
                "weak": 2.0,
                "poor": 1.0,
            },
        }

        for label, value in band_map.get(rubric_section, {}).items():
            if label in normalized:
                return value

        return None

    def _ensure_deck_storage_path_column(self, cur) -> None:
        cur.execute(
            '''
            ALTER TABLE DECK
            ADD COLUMN IF NOT EXISTS storage_object_path TEXT
            '''
        )

    def _ensure_deck_owner_column(self, cur) -> None:
        cur.execute(
            '''
            ALTER TABLE DECK
            ADD COLUMN IF NOT EXISTS owner_id UUID
            '''
        )

    def _ensure_deck_visibility_column(self, cur) -> None:
        cur.execute(
            '''
            ALTER TABLE DECK
            ADD COLUMN IF NOT EXISTS visible_to_vcs BOOLEAN NOT NULL DEFAULT FALSE
            '''
        )

    def _ensure_deck_embedding_facet_table(self, cur) -> None:
        cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS DECK_EMBEDDING_FACET (
                deck_id TEXT NOT NULL,
                facet_type TEXT NOT NULL,
                facet_title TEXT NOT NULL,
                facet_text TEXT NOT NULL,
                embedding VECTOR(768) NOT NULL,
                embedding_model TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (deck_id, facet_type),
                FOREIGN KEY (deck_id) REFERENCES DECK(deck_id) ON DELETE CASCADE
            )
            '''
        )
        cur.execute(
            '''
            CREATE INDEX IF NOT EXISTS deck_embedding_facet_embedding_idx
            ON DECK_EMBEDDING_FACET
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            '''
        )

    def _ensure_score_detail_columns(self, cur) -> None:
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS raw_score TEXT
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS feedback TEXT
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS evidence TEXT
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS confidence NUMERIC
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS adjusted_value NUMERIC
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS confidence_reason TEXT
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS verification_status TEXT
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS critic_notes TEXT
            '''
        )
        cur.execute(
            '''
            ALTER TABLE SCORE
            ADD COLUMN IF NOT EXISTS external_checks JSONB
            '''
        )

    def _ensure_user_profile_table(self, cur) -> None:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS USER_PROFILE (
                user_id UUID PRIMARY KEY,
                profile_type TEXT NOT NULL CHECK (profile_type IN ('startup', 'vc')),
                organization_name TEXT NOT NULL,
                website TEXT NOT NULL,
                role_title TEXT NOT NULL,
                sector_focus TEXT NOT NULL,
                geography TEXT NOT NULL,
                description TEXT NOT NULL,
                startup_stage TEXT,
                fund_stage_focus TEXT,
                check_size_range TEXT,
                fundraising_status TEXT,
                target_raise TEXT,
                traction_summary TEXT,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            '''
        )

    def retrieve_user_profile(self, conn, user_id: str):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_user_profile_table(cur)
        cur.execute(
            '''
            SELECT
                user_id,
                profile_type,
                organization_name,
                website,
                role_title,
                sector_focus,
                geography,
                description,
                startup_stage,
                fund_stage_focus,
                check_size_range,
                fundraising_status,
                target_raise,
                traction_summary,
                notes,
                created_at,
                updated_at
            FROM USER_PROFILE
            WHERE user_id = %s
            ''',
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def get_user_profile_type(self, conn, user_id: str) -> str | None:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_user_profile_table(cur)
        cur.execute(
            '''
            SELECT profile_type
            FROM USER_PROFILE
            WHERE user_id = %s
            ''',
            (user_id,),
        )
        row = cur.fetchone()
        return row["profile_type"] if row else None

    def upsert_user_profile(self, conn, user_id: str, profile: dict):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_user_profile_table(cur)
        cur.execute(
            '''
            INSERT INTO USER_PROFILE (
                user_id,
                profile_type,
                organization_name,
                website,
                role_title,
                sector_focus,
                geography,
                description,
                startup_stage,
                fund_stage_focus,
                check_size_range,
                fundraising_status,
                target_raise,
                traction_summary,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                profile_type = EXCLUDED.profile_type,
                organization_name = EXCLUDED.organization_name,
                website = EXCLUDED.website,
                role_title = EXCLUDED.role_title,
                sector_focus = EXCLUDED.sector_focus,
                geography = EXCLUDED.geography,
                description = EXCLUDED.description,
                startup_stage = EXCLUDED.startup_stage,
                fund_stage_focus = EXCLUDED.fund_stage_focus,
                check_size_range = EXCLUDED.check_size_range,
                fundraising_status = EXCLUDED.fundraising_status,
                target_raise = EXCLUDED.target_raise,
                traction_summary = EXCLUDED.traction_summary,
                notes = EXCLUDED.notes,
                updated_at = NOW()
            RETURNING
                user_id,
                profile_type,
                organization_name,
                website,
                role_title,
                sector_focus,
                geography,
                description,
                startup_stage,
                fund_stage_focus,
                check_size_range,
                fundraising_status,
                target_raise,
                traction_summary,
                notes,
                created_at,
                updated_at
            ''',
            (
                user_id,
                profile["profile_type"],
                profile["organization_name"],
                profile["website"],
                profile["role_title"],
                profile["sector_focus"],
                profile["geography"],
                profile["description"],
                profile.get("startup_stage"),
                profile.get("fund_stage_focus"),
                profile.get("check_size_range"),
                profile.get("fundraising_status"),
                profile.get("target_raise"),
                profile.get("traction_summary"),
                profile.get("notes"),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)

    def _build_score_summary(self, conn, deck_id: str):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_score_detail_columns(cur)
        cur.execute(
            '''
            SELECT
                rubric_section,
                value,
                raw_score,
                feedback,
                evidence,
                confidence,
                adjusted_value,
                confidence_reason,
                verification_status,
                critic_notes,
                external_checks
            FROM SCORE
            WHERE deck_id = %s
            ORDER BY rubric_section ASC
            ''',
            (deck_id,),
        )
        score_rows = cur.fetchall()

        cur.execute(
            '''
            SELECT COUNT(*) AS red_flag_count
            FROM RED_FLAG
            WHERE deck_id = %s
            ''',
            (deck_id,),
        )
        red_flag_row = cur.fetchone() or {"red_flag_count": 0}

        cur.execute(
            '''
            SELECT flag_type
            FROM RED_FLAG
            WHERE deck_id = %s
            ORDER BY red_flag_id ASC
            ''',
            (deck_id,),
        )
        red_flag_rows = cur.fetchall()

        numeric_scores = [float(row["value"]) for row in score_rows if row.get("value") is not None]
        adjusted_scores = [
            float(row["adjusted_value"] if row.get("adjusted_value") is not None else row["value"])
            for row in score_rows
            if row.get("value") is not None
        ]
        breakdown = [
            {
                "rubric_section": row["rubric_section"],
                "value": float(row["value"]) if row.get("value") is not None else None,
                "raw_score": row.get("raw_score"),
                "feedback": row.get("feedback"),
                "evidence": row.get("evidence"),
                "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
                "adjusted_value": float(row["adjusted_value"]) if row.get("adjusted_value") is not None else None,
                "confidence_reason": row.get("confidence_reason"),
                "verification_status": row.get("verification_status"),
                "critic_notes": row.get("critic_notes"),
                "external_checks": self._parse_json_list(row.get("external_checks"), []),
            }
            for row in score_rows
        ]

        if not score_rows:
            return None

        return {
            "overall_score": round(sum(adjusted_scores), 1) if adjusted_scores else None,
            "raw_overall_score": round(sum(numeric_scores), 1) if numeric_scores else None,
            "confidence_adjusted_overall_score": round(sum(adjusted_scores), 1) if adjusted_scores else None,
            "scored_sections": len(numeric_scores),
            "red_flag_count": int(red_flag_row.get("red_flag_count") or 0),
            "red_flags": [row["flag_type"] for row in red_flag_rows if row.get("flag_type")],
            "score_breakdown": breakdown,
        }

    def _parse_json_list(self, value, default):
        if value is None:
            return default
        if isinstance(value, list):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else default
        except (TypeError, json.JSONDecodeError):
            return default

    def _normalize_text(self, value) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _source_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _vector_literal(self, embedding: list[float]) -> str:
        return "[" + ",".join(str(float(value)) for value in embedding) + "]"

    def _append_line(self, lines: list[str], label: str, value) -> None:
        normalized = self._normalize_text(value)
        if normalized:
            lines.append(f"{label}: {normalized}")

    def _join_limited(self, parts: list[str], max_chars: int = 7000) -> str:
        text = "\n".join(part for part in parts if self._normalize_text(part))
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit("\n", 1)[0] or text[:max_chars]

    def _get_deck_context(self, conn, deck_id: str):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_score_detail_columns(cur)
        cur.execute(
            '''
            SELECT deck_id, company_name, sector, stage, team
            FROM DECK
            WHERE deck_id = %s
            ''',
            (deck_id,),
        )
        deck = cur.fetchone()
        if deck is None:
            raise ValueError(f"No deck found for deck_id={deck_id}")

        cur.execute(
            '''
            SELECT slide_number, slide_section, extracted_text, graphic_path
            FROM SLIDE
            WHERE deck_id = %s
            ORDER BY slide_number ASC
            ''',
            (deck_id,),
        )
        slides = cur.fetchall()

        cur.execute(
            '''
            SELECT rubric_section, value, raw_score, feedback, evidence
            FROM SCORE
            WHERE deck_id = %s
            ORDER BY rubric_section ASC
            ''',
            (deck_id,),
        )
        scores = cur.fetchall()

        cur.execute(
            '''
            SELECT flag_type
            FROM RED_FLAG
            WHERE deck_id = %s
            ORDER BY red_flag_id ASC
            ''',
            (deck_id,),
        )
        red_flags = cur.fetchall()

        return {
            "deck": deck,
            "slides": slides,
            "scores": scores,
            "red_flags": red_flags,
        }

    def _slides_for_sections(self, context: dict, sections: set[str]) -> list[str]:
        lines = []
        for slide in context["slides"]:
            section = self._normalize_text(slide.get("slide_section")) or "Unknown"
            if section not in sections:
                continue
            slide_lines = [f"Slide {slide.get('slide_number')} [{section}]"]
            self._append_line(slide_lines, "Text", slide.get("extracted_text"))
            visuals = self._parse_json_list(slide.get("graphic_path"), [])
            if visuals:
                self._append_line(slide_lines, "Visuals", "; ".join(self._normalize_text(item) for item in visuals if self._normalize_text(item)))
            lines.append(self._join_limited(slide_lines, max_chars=1600))
        return lines

    def _scores_for_sections(self, context: dict, sections: set[str]) -> list[str]:
        lines = []
        for score in context["scores"]:
            section = self._normalize_text(score.get("rubric_section"))
            if section not in sections:
                continue
            score_lines = [f"Evaluation: {section}"]
            self._append_line(score_lines, "Score", score.get("raw_score") or score.get("value"))
            self._append_line(score_lines, "Feedback", score.get("feedback"))
            self._append_line(score_lines, "Evidence", score.get("evidence"))
            lines.append(self._join_limited(score_lines, max_chars=1200))
        return lines

    def build_deck_embedding_facets(self, conn, deck_id: str):
        context = self._get_deck_context(conn, deck_id)
        deck = context["deck"]
        team = self._parse_json_list(deck.get("team"), [])
        score_summary = self._build_score_summary(conn, deck_id)

        def make_facet(facet_type: str, title: str, lines: list[str]):
            facet_text = self._join_limited(lines, max_chars=7000)
            if not facet_text:
                return None
            return {
                "facet_type": facet_type,
                "facet_title": title,
                "facet_text": facet_text,
                "source_hash": self._source_hash(facet_text),
            }

        facets = []
        metadata_lines = []
        self._append_line(metadata_lines, "Company", deck.get("company_name"))
        self._append_line(metadata_lines, "Sector", deck.get("sector"))
        self._append_line(metadata_lines, "Stage", deck.get("stage"))
        self._append_line(metadata_lines, "Team", ", ".join(self._normalize_text(member) for member in team if self._normalize_text(member)))
        if score_summary and score_summary.get("overall_score") is not None:
            self._append_line(metadata_lines, "Readiness score", f"{score_summary['overall_score']} out of 110")
        facets.append(make_facet("company_snapshot", "Company Snapshot", metadata_lines))

        problem_solution = {"Problem", "Solution", "Product & Tech"}
        facets.append(make_facet(
            "problem_solution",
            "Problem, Solution, Product",
            self._slides_for_sections(context, problem_solution) + self._scores_for_sections(context, problem_solution),
        ))

        market_gtm = {"Market Size", "Business Model", "Go-To-Market", "Competition"}
        facets.append(make_facet(
            "market_gtm",
            "Market, Business Model, GTM",
            self._slides_for_sections(context, market_gtm) + self._scores_for_sections(context, market_gtm),
        ))

        team_traction = {"Team", "Traction & KPIs", "The Ask & Financials"}
        facets.append(make_facet(
            "team_traction",
            "Team, Traction, Ask",
            self._slides_for_sections(context, team_traction) + self._scores_for_sections(context, team_traction),
        ))

        risk_lines = []
        for flag in context["red_flags"]:
            self._append_line(risk_lines, "Red flag", flag.get("flag_type"))
        for score in context["scores"]:
            value = score.get("value")
            if value is not None and float(value) <= 3:
                self._append_line(risk_lines, f"Weak section {score.get('rubric_section')}", score.get("feedback") or score.get("raw_score"))
        if score_summary:
            self._append_line(risk_lines, "Red flag count", score_summary.get("red_flag_count"))
            self._append_line(risk_lines, "Scored sections", score_summary.get("scored_sections"))
        facets.append(make_facet("risk_quality", "Risks and Quality Signals", risk_lines))

        return [facet for facet in facets if facet]

    def upsert_deck_embedding_facets(
        self,
        conn,
        deck_id: str,
        embed_text: Callable[[str], list[float]],
        embedding_model: str,
    ) -> int:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_embedding_facet_table(cur)
        facets = self.build_deck_embedding_facets(conn, deck_id)
        facet_types = [facet["facet_type"] for facet in facets]
        if facet_types:
            cur.execute(
                '''
                DELETE FROM DECK_EMBEDDING_FACET
                WHERE deck_id = %s AND facet_type <> ALL(%s)
                ''',
                (deck_id, facet_types),
            )
        else:
            cur.execute('DELETE FROM DECK_EMBEDDING_FACET WHERE deck_id = %s', (deck_id,))
            conn.commit()
            return 0

        updated_count = 0
        for facet in facets:
            cur.execute(
                '''
                SELECT source_hash, embedding_model
                FROM DECK_EMBEDDING_FACET
                WHERE deck_id = %s AND facet_type = %s
                ''',
                (deck_id, facet["facet_type"]),
            )
            existing = cur.fetchone()
            if existing and existing["source_hash"] == facet["source_hash"] and existing["embedding_model"] == embedding_model:
                continue

            embedding = embed_text(facet["facet_text"])
            cur.execute(
                '''
                INSERT INTO DECK_EMBEDDING_FACET (
                    deck_id,
                    facet_type,
                    facet_title,
                    facet_text,
                    embedding,
                    embedding_model,
                    source_hash
                )
                VALUES (%s, %s, %s, %s, %s::vector, %s, %s)
                ON CONFLICT (deck_id, facet_type) DO UPDATE SET
                    facet_title = EXCLUDED.facet_title,
                    facet_text = EXCLUDED.facet_text,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    source_hash = EXCLUDED.source_hash,
                    updated_at = NOW()
                ''',
                (
                    deck_id,
                    facet["facet_type"],
                    facet["facet_title"],
                    facet["facet_text"],
                    self._vector_literal(embedding),
                    embedding_model,
                    facet["source_hash"],
                ),
            )
            updated_count += 1
        conn.commit()
        return updated_count

    def ensure_visible_deck_embedding_facets(
        self,
        conn,
        embed_text: Callable[[str], list[float]],
        embedding_model: str,
        limit: int = 3,
    ) -> int:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_owner_column(cur)
        self._ensure_deck_visibility_column(cur)
        self._ensure_deck_embedding_facet_table(cur)
        cur.execute(
            '''
            SELECT deck_id
            FROM DECK
            WHERE visible_to_vcs = TRUE
            ORDER BY company_name ASC
            LIMIT %s
            ''',
            (limit,),
        )
        updated = 0
        for row in cur.fetchall():
            updated += self.upsert_deck_embedding_facets(conn, row["deck_id"], embed_text, embedding_model)
        return updated

    def build_vc_query_text(self, profile: dict) -> str:
        lines = []
        self._append_line(lines, "Investor firm", profile.get("organization_name"))
        self._append_line(lines, "Investor role", profile.get("role_title"))
        self._append_line(lines, "Investment thesis", profile.get("description"))
        self._append_line(lines, "Sector focus", profile.get("sector_focus"))
        self._append_line(lines, "Stage focus", profile.get("fund_stage_focus"))
        self._append_line(lines, "Geography focus", profile.get("geography"))
        self._append_line(lines, "Check size range", profile.get("check_size_range"))
        self._append_line(lines, "Notes", profile.get("notes"))
        return self._join_limited(lines, max_chars=4000)

    def _keyword_overlap_score(self, focus_text: str | None, target_text: str | None) -> float:
        focus = {
            word
            for word in re.split(r"[^a-z0-9]+", (focus_text or "").lower())
            if len(word) >= 3
        }
        target = {
            word
            for word in re.split(r"[^a-z0-9]+", (target_text or "").lower())
            if len(word) >= 3
        }
        if not focus or not target:
            return 0.0
        return len(focus & target) / max(1, len(focus))

    def _format_match_reason(self, deck: dict, profile: dict, top_facets: list[dict], structured_score: float) -> str:
        reasons = []
        if self._keyword_overlap_score(profile.get("sector_focus"), deck.get("sector")) > 0:
            reasons.append(f"sector fit with {deck.get('sector')}")
        if self._keyword_overlap_score(profile.get("fund_stage_focus"), deck.get("stage")) > 0:
            reasons.append(f"stage fit with {deck.get('stage')}")
        if top_facets:
            reasons.append(f"strongest signal: {top_facets[0]['facet_title']}")
        if not reasons and structured_score > 0:
            reasons.append("profile filters partially match")
        return "; ".join(reasons) if reasons else "semantic fit based on investment thesis"

    def list_decks_ranked_for_vc(
        self,
        conn,
        owner_id: str,
        is_admin: bool,
        vc_profile: dict,
        query_embedding: list[float],
    ):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_owner_column(cur)
        self._ensure_deck_visibility_column(cur)
        self._ensure_deck_embedding_facet_table(cur)
        visibility_clause = "TRUE" if is_admin else "(DECK.visible_to_vcs = TRUE OR DECK.owner_id = %s)"
        params = [self._vector_literal(query_embedding)]
        if not is_admin:
            params.append(owner_id)
        cur.execute(
            f'''
            SELECT
                DECK.deck_id,
                DECK.company_name,
                DECK.sector,
                DECK.stage,
                DECK.team,
                DECK.storage_object_path,
                DECK.owner_id,
                DECK.visible_to_vcs,
                DECK_EMBEDDING_FACET.facet_type,
                DECK_EMBEDDING_FACET.facet_title,
                CASE
                    WHEN DECK_EMBEDDING_FACET.embedding IS NULL THEN NULL
                    ELSE 1 - (DECK_EMBEDDING_FACET.embedding <=> %s::vector)
                END AS similarity
            FROM DECK
            LEFT JOIN DECK_EMBEDDING_FACET
                ON DECK_EMBEDDING_FACET.deck_id = DECK.deck_id
            WHERE {visibility_clause}
            ORDER BY DECK.company_name ASC
            ''',
            tuple(params),
        )
        rows = cur.fetchall()

        grouped: dict[str, dict] = {}
        for row in rows:
            deck_id = row["deck_id"]
            if deck_id not in grouped:
                grouped[deck_id] = {
                    "row": row,
                    "facets": [],
                }
            if row.get("facet_type") and row.get("similarity") is not None:
                grouped[deck_id]["facets"].append(
                    {
                        "facet_type": row["facet_type"],
                        "facet_title": row["facet_title"],
                        "score": float(row["similarity"]),
                    }
                )

        decks = []
        for deck_id, grouped_item in grouped.items():
            row = grouped_item["row"]
            facets = sorted(grouped_item["facets"], key=lambda item: item["score"], reverse=True)
            top_facets = facets[:3]
            semantic_best = top_facets[0]["score"] if top_facets else 0.0
            semantic_average = sum(item["score"] for item in top_facets) / len(top_facets) if top_facets else 0.0
            sector_score = self._keyword_overlap_score(vc_profile.get("sector_focus"), row.get("sector"))
            stage_score = self._keyword_overlap_score(vc_profile.get("fund_stage_focus"), row.get("stage"))
            structured_score = min(1.0, (sector_score * 0.6) + (stage_score * 0.4))
            score_summary = self._build_score_summary(conn, deck_id)
            quality_score = 0.0
            if score_summary and score_summary.get("overall_score") is not None:
                quality_score = min(1.0, max(0.0, float(score_summary["overall_score"]) / 110.0))
            hybrid_score = (semantic_best * 0.50) + (semantic_average * 0.20) + (structured_score * 0.20) + (quality_score * 0.10)
            decks.append(
                {
                    "deck_id": row["deck_id"],
                    "company_name": row["company_name"] or "",
                    "sector": row["sector"] or "",
                    "stage": row["stage"] or "",
                    "team": self._parse_json_list(row["team"], []),
                    "storage_object_path": row.get("storage_object_path"),
                    "visible_to_vcs": bool(row.get("visible_to_vcs")),
                    "can_manage_visibility": bool(str(row.get("owner_id")) == owner_id or is_admin),
                    "score_summary": score_summary,
                    "match_score": round(max(0.0, min(1.0, hybrid_score)) * 100, 1),
                    "match_reason": self._format_match_reason(row, vc_profile, top_facets, structured_score),
                    "matched_facets": [
                        {
                            "facet_type": item["facet_type"],
                            "facet_title": item["facet_title"],
                            "score": round(max(0.0, min(1.0, item["score"])) * 100, 1),
                        }
                        for item in top_facets
                    ],
                }
            )

        return sorted(decks, key=lambda item: item.get("match_score") or 0, reverse=True)


    def ingest_deck(
        self,
        conn,
        evaluation: PitchDeckEvaluation | Deck,
        eval_included: bool = False,
        storage_object_path: str | None = None,
        owner_id: str | None = None,
        visible_to_vcs: bool = False,
    ):
        cur = conn.cursor()
        deck = evaluation.deck if isinstance(evaluation, PitchDeckEvaluation) else evaluation
        pitch_evaluation = evaluation if isinstance(evaluation, PitchDeckEvaluation) else None

        if deck is None:
            raise ValueError("Deck data is required for ingestion")

        if not owner_id:
            raise ValueError("owner_id is required for deck ingestion")

        deck_id = self._make_deck_id(deck, owner_id)
        self._ensure_deck_storage_path_column(cur)
        self._ensure_deck_owner_column(cur)
        self._ensure_deck_visibility_column(cur)

        cur.execute(
            '''
            INSERT INTO DECK (deck_id, company_name, sector, stage, team, storage_object_path, owner_id, visible_to_vcs)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                deck_id,
                deck.company,
                deck.sector,
                deck.stage,
                json.dumps(deck.team, ensure_ascii=False),
                storage_object_path,
                owner_id,
                visible_to_vcs,
            )
        )

        for slide in deck.slides:
            cur.execute(
                '''
                INSERT INTO SLIDE (slide_id, deck_id, slide_number, slide_section, extracted_text, graphic_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''',
                (
                    f"{deck_id}_slide_{slide.slide_number}",
                    deck_id,
                    slide.slide_number,
                    slide.section,
                    slide.text,
                    json.dumps(slide.graph_desc, ensure_ascii=False),
                )
            )
        conn.commit()
        if eval_included and pitch_evaluation is not None:
            self.ingest_evaluation(conn, deck_id, pitch_evaluation)
        conn.close()
        
    def ingest_evaluation(self, conn, deck_id, evaluation : PitchDeckEvaluation):
        cur = conn.cursor()
        self._ensure_score_detail_columns(cur)
        rubric_sections = [
            ("Problem", evaluation.s1_problem),
            ("Solution", evaluation.s2_solution),
            ("Market Size", evaluation.s3_market_size),
            ("Product & Tech", evaluation.s4_product_and_tech),
            ("Business Model", evaluation.s5_business_model),
            ("Go-To-Market", evaluation.s6_go_to_market),
            ("Competition", evaluation.s7_competition),
            ("Team", evaluation.s8_team),
            ("Traction & KPIs", evaluation.s9_traction_and_kpis),
            ("The Ask & Financials", evaluation.s10_the_ask_and_financials),
        ]

        for index, (rubric_section, section) in enumerate(rubric_sections, start=1):
            normalized_score = self._normalize_score_value(rubric_section, section.score) if section.is_present else None
            adjusted_value = section.adjusted_score
            if adjusted_value is None and normalized_score is not None and section.confidence is not None:
                adjusted_value = round(normalized_score * float(section.confidence), 1)
            external_checks = [
                check.model_dump(mode="json") if hasattr(check, "model_dump") else check
                for check in (section.external_checks or [])
            ]
            cur.execute(
                '''
                INSERT INTO SCORE (
                    score_id,
                    deck_id,
                    rubric_section,
                    value,
                    raw_score,
                    feedback,
                    evidence,
                    confidence,
                    adjusted_value,
                    confidence_reason,
                    verification_status,
                    critic_notes,
                    external_checks
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''',
                (
                    f"{deck_id}_score_{index}",
                    deck_id,
                    rubric_section,
                    normalized_score,
                    None if section.score is None else str(section.score),
                    section.feedback if section.is_present else None,
                    section.evidence if section.is_present else None,
                    section.confidence,
                    adjusted_value,
                    section.confidence_reason,
                    section.verification_status,
                    section.critic_notes,
                    json.dumps(external_checks, ensure_ascii=False),
                )
            )

        for index, red_flag in enumerate(evaluation.red_flags, start=1):
            cur.execute(
                '''
                INSERT INTO RED_FLAG (red_flag_id, deck_id, slide_id, flag_type)
                VALUES (%s, %s, %s, %s)
                ''',
                (
                    f"{deck_id}_red_flag_{index}",
                    deck_id,
                    None,
                    red_flag,
                )
            )
        conn.commit()
    
    def retrieve_deck(self, conn, deck_id, owner_id: str, is_admin : bool, viewer_is_vc: bool = False):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_visibility_column(cur)
        if is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
                FROM DECK
                WHERE deck_id = %s
                ''',
                (deck_id,),
            )
            deck_row = cur.fetchone()
        else:
            self._ensure_deck_owner_column(cur)
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
                FROM DECK
                WHERE deck_id = %s
                AND (owner_id = %s OR owner_id IS NULL OR (%s AND visible_to_vcs = TRUE))
                ''',
                (deck_id, owner_id, viewer_is_vc),
            )
            deck_row = cur.fetchone()

        if deck_row is None:
            raise ValueError(f"No deck found for deck_id={deck_id}")

        cur.execute(
            '''
            SELECT slide_number, slide_section, extracted_text, graphic_path
            FROM SLIDE
            WHERE deck_id = %s
            ORDER BY slide_number
            ''',
            (deck_id,),
        )
        slide_rows = cur.fetchall()

        def _parse_json_list(value, default):
            if value is None:
                return default
            if isinstance(value, list):
                return value
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else default
            except (TypeError, json.JSONDecodeError):
                return default

        team = _parse_json_list(deck_row["team"], [])
        slides = []
        for row in slide_rows:
            slides.append(
                DeckSlide(
                    slide_number=row["slide_number"],
                    text=row["extracted_text"] or "",
                    graph_desc=_parse_json_list(row["graphic_path"], []),
                    section=row["slide_section"] or "",
                )
            )

        return Deck(
            title=deck_row["company_name"],
            company=deck_row["company_name"],
            team=team,
            stage=deck_row["stage"] or "",
            sector=deck_row["sector"] or "",
            slides=slides,
        )

    def list_decks(self, conn, owner_id: str, is_admin : bool, viewer_is_vc: bool = False):
        cur : psycopg2.extras.RealDictCursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_owner_column(cur)
        self._ensure_deck_visibility_column(cur)
        if is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path, owner_id, visible_to_vcs
                FROM DECK
                ORDER BY company_name ASC
                LIMIT 10
                ''',
            )
            rows = cur.fetchall()
        else:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path, owner_id, visible_to_vcs
                FROM DECK
                WHERE owner_id = %s OR (%s AND visible_to_vcs = TRUE)
                ORDER BY company_name ASC
                ''',
                (owner_id, viewer_is_vc),
            )
            rows = cur.fetchall()

        if not rows and not is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path, owner_id, visible_to_vcs
                FROM DECK
                WHERE owner_id IS NULL
                ORDER BY company_name ASC
                ''',
            )
            rows = cur.fetchall()
        def _parse_json_list(value, default):
            if value is None:
                return default
            if isinstance(value, list):
                return value
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else default
            except (TypeError, json.JSONDecodeError):
                return default

        decks = []
        for row in rows:
            decks.append(
                {
                    "deck_id": row["deck_id"],
                    "company_name": row["company_name"] or "",
                    "sector": row["sector"] or "",
                    "stage": row["stage"] or "",
                    "team": _parse_json_list(row["team"], []),
                    "storage_object_path": row.get("storage_object_path"),
                    "visible_to_vcs": bool(row.get("visible_to_vcs")),
                    "can_manage_visibility": bool(str(row.get("owner_id")) == owner_id or is_admin),
                    "score_summary": self._build_score_summary(conn, row["deck_id"]),
                }
            )
        return decks

    def retrieve_deck_metadata(self, conn, deck_id, owner_id: str, is_admin : bool, viewer_is_vc: bool = False):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_visibility_column(cur)
        if is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path, owner_id, visible_to_vcs
                FROM DECK
                WHERE deck_id = %s
                ''',
                (deck_id,),
            )
            row = cur.fetchone()
        else: 
            self._ensure_deck_owner_column(cur)
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path, owner_id, visible_to_vcs
                FROM DECK
                WHERE deck_id = %s
                AND (owner_id = %s OR owner_id IS NULL OR (%s AND visible_to_vcs = TRUE))
                ''',
                (deck_id, owner_id, viewer_is_vc),
            )
            row = cur.fetchone()
        if row is None:
            raise ValueError(f"No deck found for deck_id={deck_id}")

        def _parse_json_list(value, default):
            if value is None:
                return default
            if isinstance(value, list):
                return value
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else default
            except (TypeError, json.JSONDecodeError):
                return default

        return {
            "deck_id": row["deck_id"],
            "company_name": row["company_name"] or "",
            "sector": row["sector"] or "",
            "stage": row["stage"] or "",
            "team": _parse_json_list(row["team"], []),
            "storage_object_path": row.get("storage_object_path"),
            "visible_to_vcs": bool(row.get("visible_to_vcs")),
            "can_manage_visibility": bool(str(row.get("owner_id")) == owner_id or is_admin),
            "score_summary": self._build_score_summary(conn, deck_id),
        }

    def retrieve_slides(self, conn, deck_id, owner_id: str, is_admin : bool, viewer_is_vc: bool = False):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_visibility_column(cur)
        if is_admin:
            cur.execute(
                '''
                SELECT slide_number, slide_section, extracted_text, graphic_path
                FROM SLIDE
                JOIN DECK ON DECK.deck_id = SLIDE.deck_id
                WHERE SLIDE.deck_id = %s
                ORDER BY slide_number
                ''',
                (deck_id,),
            )
            rows = cur.fetchall()
        else:
            self._ensure_deck_owner_column(cur)
            cur.execute(
                '''
                SELECT slide_number, slide_section, extracted_text, graphic_path
                FROM SLIDE
                JOIN DECK ON DECK.deck_id = SLIDE.deck_id
                WHERE SLIDE.deck_id = %s
                AND (DECK.owner_id = %s OR DECK.owner_id IS NULL OR (%s AND DECK.visible_to_vcs = TRUE))
                ORDER BY slide_number
                ''',
                (deck_id, owner_id, viewer_is_vc),
            )
            rows = cur.fetchall()
        if not rows:
            if is_admin:
                cur.execute(
                    '''
                    SELECT 1
                    FROM DECK
                    WHERE deck_id = %s
                    ''',
                    (deck_id,),
                )
                deck_exists = cur.fetchone()
            else:
                cur.execute(
                    '''
                    SELECT 1
                    FROM DECK
                    WHERE deck_id = %s
                    AND (owner_id = %s OR owner_id IS NULL OR (%s AND visible_to_vcs = TRUE))
                    ''',
                    (deck_id, owner_id, viewer_is_vc),
                )
                deck_exists = cur.fetchone()
            if deck_exists is None:
                raise ValueError(f"No deck found for deck_id={deck_id}")

        def _parse_json_list(value, default):
            if value is None:
                return default
            if isinstance(value, list):
                return value
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else default
            except (TypeError, json.JSONDecodeError):
                return default

        slides = []
        for row in rows:
            slides.append(
                {
                    "slide_number": row["slide_number"],
                    "text": row["extracted_text"] or "",
                    "graph_desc": _parse_json_list(row["graphic_path"], []),
                    "section": row["slide_section"] or "",
                }
            )
        return slides

    def update_deck_visibility(self, conn, deck_id: str, owner_id: str, visible_to_vcs: bool, is_admin: bool = False):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_owner_column(cur)
        self._ensure_deck_visibility_column(cur)
        if is_admin:
            cur.execute(
                '''
                UPDATE DECK
                SET visible_to_vcs = %s
                WHERE deck_id = %s
                RETURNING deck_id, owner_id, visible_to_vcs
                ''',
                (visible_to_vcs, deck_id),
            )
        else:
            cur.execute(
                '''
                UPDATE DECK
                SET visible_to_vcs = %s
                WHERE deck_id = %s AND owner_id = %s
                RETURNING deck_id, owner_id, visible_to_vcs
                ''',
                (visible_to_vcs, deck_id, owner_id),
            )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No deck found for deck_id={deck_id}")
        conn.commit()
        return {
            "deck_id": row["deck_id"],
            "visible_to_vcs": bool(row["visible_to_vcs"]),
            "can_manage_visibility": bool(str(row.get("owner_id")) == owner_id or is_admin),
        }

    def delete_deck(self, conn, deck_id: str, owner_id: str, is_admin: bool = False):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_owner_column(cur)
        if is_admin:
            cur.execute(
                '''
                SELECT deck_id, storage_object_path
                FROM DECK
                WHERE deck_id = %s
                ''',
                (deck_id,),
            )
        else:
            cur.execute(
                '''
                SELECT deck_id, storage_object_path
                FROM DECK
                WHERE deck_id = %s AND owner_id = %s
                ''',
                (deck_id, owner_id),
            )
        deck_row = cur.fetchone()

        if deck_row is None:
            raise ValueError(f"No deck found for deck_id={deck_id}")

        cur.execute('DELETE FROM RED_FLAG WHERE deck_id = %s', (deck_id,))
        cur.execute('DELETE FROM SCORE WHERE deck_id = %s', (deck_id,))
        cur.execute('DELETE FROM SLIDE WHERE deck_id = %s', (deck_id,))
        cur.execute('DELETE FROM DECK WHERE deck_id = %s', (deck_id,))
        conn.commit()

        return {
            "deck_id": deck_row["deck_id"],
            "storage_object_path": deck_row.get("storage_object_path"),
        }

class TestUpsert(unittest.TestCase):
    def testupsert(self):
        db = SQLDatabase()
        DATABASE_URL = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(DATABASE_URL)
        deck = db.load_deck_from_json("sample_startup_deck.json")
        self.assertIsInstance(deck, Deck)
        self.assertGreater(len(deck.slides), 0)
        retrieved : Deck = db.retrieve_deck(conn, "1906", "00000000-0000-0000-0000-000000000000", True)
        self.assertEqual(retrieved.company, deck.company)
        self.assertEqual(retrieved.team, deck.team)

        
        
if __name__ == "__main__":
    unittest.main()
    # Example usage:
    # evaluation = parser.evaluate_pitch_deck("sample_startup_deck.pdf")
    # ingest_deck(conn, evaluation)
    # print("PitchDeckEvaluation ingested.")
    
    
    
