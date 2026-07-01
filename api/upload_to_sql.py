import json
import hashlib
import os
import re
import unittest

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
                "clear": 3.0,
                "present": 2.0,
                "adequate": 2.0,
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
                "exceptional": 9.5,
                "strong": 7.5,
                "adequate": 5.5,
                "weak": 3.5,
                "poor": 1.5,
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
                "exceptional": 9.5,
                "strong": 7.5,
                "adequate": 5.5,
                "weak": 3.5,
                "poor": 1.5,
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

    def _build_score_summary(self, conn, deck_id: str):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_score_detail_columns(cur)
        cur.execute(
            '''
            SELECT rubric_section, value, raw_score, feedback, evidence
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
        print(numeric_scores)
        breakdown = [
            {
                "rubric_section": row["rubric_section"],
                "value": float(row["value"]) if row.get("value") is not None else None,
                "raw_score": row.get("raw_score"),
                "feedback": row.get("feedback"),
                "evidence": row.get("evidence"),
            }
            for row in score_rows
        ]

        if not score_rows:
            return None

        return {
            "overall_score": round(sum(numeric_scores), 1) if numeric_scores else None,
            "scored_sections": len(numeric_scores),
            "red_flag_count": int(red_flag_row.get("red_flag_count") or 0),
            "red_flags": [row["flag_type"] for row in red_flag_rows if row.get("flag_type")],
            "score_breakdown": breakdown,
        }


    def ingest_deck(
        self,
        conn,
        evaluation: PitchDeckEvaluation | Deck,
        eval_included: bool = False,
        storage_object_path: str | None = None,
        owner_id: str | None = None,
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

        cur.execute(
            '''
            INSERT INTO DECK (deck_id, company_name, sector, stage, team, storage_object_path, owner_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                deck_id,
                deck.company,
                deck.sector,
                deck.stage,
                json.dumps(deck.team, ensure_ascii=False),
                storage_object_path,
                owner_id,
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
            cur.execute(
                '''
                INSERT INTO SCORE (score_id, deck_id, rubric_section, value, raw_score, feedback, evidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''',
                (
                    f"{deck_id}_score_{index}",
                    deck_id,
                    rubric_section,
                    self._normalize_score_value(rubric_section, section.score) if section.is_present else None,
                    None if section.score is None else str(section.score),
                    section.feedback if section.is_present else None,
                    section.evidence if section.is_present else None,
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
    
    def retrieve_deck(self, conn, deck_id, owner_id: str, is_admin : bool):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
                WHERE deck_id = %s AND (owner_id = %s OR owner_id IS NULL)
                ''',
                (deck_id, owner_id),
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

    def list_decks(self, conn, owner_id: str, is_admin : bool):
        cur : psycopg2.extras.RealDictCursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._ensure_deck_owner_column(cur)
        if is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
                FROM DECK
                ORDER BY company_name ASC
                LIMIT 10
                ''',
            )
            rows = cur.fetchall()
        else:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
                FROM DECK
                WHERE owner_id = %s
                ORDER BY company_name ASC
                ''',
                (owner_id,),
            )
            rows = cur.fetchall()

        if not rows and not is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
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
                    "score_summary": self._build_score_summary(conn, row["deck_id"]),
                }
            )
        return decks

    def retrieve_deck_metadata(self, conn, deck_id, owner_id: str, is_admin : bool):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if is_admin:
            cur.execute(
                '''
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
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
                SELECT deck_id, company_name, sector, stage, team, storage_object_path
                FROM DECK
                WHERE deck_id = %s AND (owner_id = %s OR owner_id IS NULL)
                ''',
                (deck_id, owner_id),
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
            "score_summary": self._build_score_summary(conn, deck_id),
        }

    def retrieve_slides(self, conn, deck_id, owner_id: str, is_admin : bool):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
                AND (DECK.owner_id = %s OR DECK.owner_id IS NULL)
                ORDER BY slide_number
                ''',
                (deck_id, owner_id),
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
                    WHERE deck_id = %s AND (owner_id = %s OR owner_id IS NULL)
                    ''',
                    (deck_id, owner_id),
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
    
    
    
