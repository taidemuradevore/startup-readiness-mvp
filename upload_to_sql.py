import json
import os
import unittest

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

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

    def _make_deck_id(self, deck: Deck):
        base = deck.company if deck.company else deck.title
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in base).strip("_") or "deck"


    def ingest_deck(self, conn, evaluation: PitchDeckEvaluation | Deck, eval_included: bool = False):
        cur = conn.cursor()
        deck = evaluation.deck if isinstance(evaluation, PitchDeckEvaluation) else evaluation
        pitch_evaluation = evaluation if isinstance(evaluation, PitchDeckEvaluation) else None

        if deck is None:
            raise ValueError("Deck data is required for ingestion")

        deck_id = self._make_deck_id(deck)

        cur.execute(
            '''
            INSERT INTO DECK (deck_id, company_name, sector, stage, team)
            VALUES (%s, %s, %s, %s, %s)
            ''',
            (
                deck_id,
                deck.company,
                deck.sector,
                deck.stage,
                json.dumps(deck.team, ensure_ascii=False),
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
                INSERT INTO SCORE (score_id, deck_id, rubric_section, value)
                VALUES (%s, %s, %s, %s)
                ''',
                (
                    f"{deck_id}_score_{index}",
                    deck_id,
                    rubric_section,
                    section.score if section.is_present else None,
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
    
    def retrieve_deck(self, conn, deck_id):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            '''
            SELECT deck_id, company_name, sector, stage, team
            FROM DECK
            WHERE deck_id = %s
            ''',
            (deck_id,),
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


class TestUpsert(unittest.TestCase):
    def testupsert(self):
        db = SQLDatabase()
        DATABASE_URL = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(DATABASE_URL)
        deck = db.load_deck_from_json("sample_startup_deck.json")
        self.assertIsInstance(deck, Deck)
        self.assertGreater(len(deck.slides), 0)
        retrieved : Deck = db.retrieve_deck(conn, "1906")
        self.assertEqual(retrieved.company, deck.company)
        self.assertEqual(retrieved.team, deck.team)

        
        
if __name__ == "__main__":
    unittest.main()
    # Example usage:
    # evaluation = parser.evaluate_pitch_deck("sample_startup_deck.pdf")
    # ingest_deck(conn, evaluation)
    # print("PitchDeckEvaluation ingested.")
    
    
