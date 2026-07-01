import unittest

from google import genai
import json
import os
from typing import Optional, List, Union
from pydantic import BaseModel, Field
from dotenv import load_dotenv


# ==================== PYDANTIC MODELS ====================

class GradedSection(BaseModel):
    is_present: bool = Field(
        description="True if this topic is addressed anywhere in the deck. False if completely missing."
    )
    score: Optional[Union[int, str]] = Field(
        default=None, 
        description="Grade based on the prompt rubric. Null if is_present is False."
    )
    feedback: Optional[str] = Field(
        default=None, 
        description="Teacher's feedback: What made this strong? What was missing or confusing? Null if is_present is False."
    )
    evidence: Optional[str] = Field(
        default=None, 
        description="A verbatim quote or specific slide reference that justifies the score. Null if is_present is False."
    )


class DeckSlide(BaseModel):
    slide_number: int = Field(
        description="The position/order of the slide in the deck"
    )
    text: str = Field(
        description="The body text content of the slide"
    )
    graph_desc: List[str] = Field(
        description="List of descriptions for any charts, graphs, or visual elements on the slide"
    )
    section: str = Field(
        description="The category this slide belongs to (e.g., Problem, Solution, Team, Market Size, etc.)"
    )


class Deck(BaseModel):
    title: str = Field(
        description="The main title or name of the pitch deck presentation"
    )
    company: str = Field(
        description="Company name or startup name"
    )
    team: List[str] = Field(
        description="List of founding team member names or roles"
    )
    stage: str = Field(
        description="Funding stage or company stage (e.g., Seed, Series A, Pre-revenue, Growth)"
    )
    sector: str = Field(
        description="Industry sector or vertical that the company operates in"
    )
    slides: List[DeckSlide] = Field(
        description="Slide content for deck"
    )


class KPIMetric(BaseModel):
    kpi_name: str = Field(description="Name of the metric (e.g., CAC, LTV, ARR)")
    kpi_value: str = Field(description="The numeric value or state")
    provenance: Optional[str] = Field(default=None, description="Verbatim quote backing up this KPI.")


class PitchDeckEvaluation(BaseModel):
    deck: Optional[Deck] = Field(
        default=None,
        description="Structured metadata extracted from the deck (title, company, team, stage, sector)."
    )
    
    # --- The Core 10 Grading Rubric ---
    s1_problem: GradedSection = Field(description="Is the problem acute, clearly defined, and validated?")
    s2_solution: GradedSection = Field(description="Does the product actually solve the problem elegantly? Is the value prop clear?")
    s3_market_size: GradedSection = Field(description="Is the Total Addressable Market (TAM) large enough for venture scale, and logically calculated?")
    s4_product_and_tech: GradedSection = Field(description="Is the underlying magic, technology, or IP defensible and clear?")
    s5_business_model: GradedSection = Field(description="Is it clear how the company makes money (pricing, revenue streams)?")
    s6_go_to_market: GradedSection = Field(description="Do they have a realistic, scalable strategy to acquire customers?")
    s7_competition: GradedSection = Field(description="Do they understand their rivals and clearly define their competitive advantage?")
    s8_team: GradedSection = Field(description="Does the founding team have the right domain expertise, technical skills, or prior exits?")
    s9_traction_and_kpis: GradedSection = Field(description="Is there proof of concept (revenue, pilots, user growth)?")
    s10_the_ask_and_financials: GradedSection = Field(description="Is the fundraise amount clear? Are the financial projections realistic and tied to use of funds?")
    
    # --- Extras for the VC Hunter Scope ---
    extracted_kpis: list[KPIMetric] = Field(
        default_factory=list, 
        description="List of hard KPIs found. Empty list if none."
    )
    red_flags: list[str] = Field(
        default_factory=list, 
        description="List any unrealistic projections, glaring omissions, or concerning statements."
    )
    final_grade: Optional[str] = Field(
        default=None,
        description="Overall letter grade (A+, A, B, C, D, F) based on the sum of the parts."
    )


# ==================== DECK PARSER CLASS ====================

class DeckParser:
    """
    A class that parses and evaluates startup pitch decks using Gemini 2.5 Flash LLM.
    
    This parser implements the Core 10 startup evaluation rubric, extracting structured
    data from pitch decks and providing detailed feedback and scoring.
    """
    
    def __init__(self, grade: bool = True):
        """Initialize the DeckParser with Gemini API client and load environment variables.
        
        Args:
            grade: If True, enables grading functionality. If False, only extraction is available.
        """
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        self.client = genai.Client()
        self.grade = grade
        
    def evaluate_pitch_deck(self, pdf_path: str) -> PitchDeckEvaluation:
        """
        Evaluate a pitch deck against the Core 10 rubric.
        
        Args:
            pdf_path: Path to the PDF file to evaluate.
            
        Returns:
            PitchDeckEvaluation: Structured evaluation with scores, feedback, and KPIs.
            
        Raises:
            RuntimeError: If grading is disabled (grade=False on initialization).
        """
        if not self.grade:
            raise RuntimeError("Grading is disabled. Initialize DeckParser with grade=True to enable grading.")
        
        print(f"Uploading {pdf_path} to Gemini...")
        
        # Upload the file securely to Google's servers for processing
        uploaded_file = self.client.files.upload(file=pdf_path)
        print(f"File uploaded successfully: {uploaded_file.name}")

        return self._evaluate_uploaded_file(uploaded_file)

    def _evaluation_prompt(self) -> str:
        return """
        You are an expert Venture Capital evaluator and a strict grader. 
        You are evaluating a startup pitch deck submitted as a final assignment. 
        Your task is to grade the deck based on the 'Core 10' startup principles.

        GRADING RUBRIC INSTRUCTIONS:
        
        SCORE BREAKDOWN
        CATEGORY, TIER, POINTS
        Problem, CORE	20 pts
        Solution, CORE, 20 pts
        Founder–Market Fit, CORE, 20 pts
        Market Size & Dynamics, SECONDARY, 10 pts
        Business Model, SECONDARY, 10 pts
        Distribution / GTM Strategy, SECONDARY, 10 pts
        Team Execution Capability, SECONDARY, 10 pts
        Traction & KPIs, TERTIARY, 5 pts
        Competitive Landscape, TERTIARY, 5 pts
        The Ask, OTHER, Qualitative

        SCORE THRESHOLDS
        90–110	Invest
        70–89	Strong Consideration
        55–69	Conditional Pass
        40–54	Needs Work
        < 40	Pass
        
        1. The Problem 20 Points
        Why it matters: The root of all business is a real, pressing need. No problem = no startup.

        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        17–20	Exceptional	Problem is vivid, urgent, and quantified. Pain is undeniable with data or narrative proof. Clear who suffers and why current solutions fail.
        13–16	Strong	Problem is clearly stated and relevant. Audience and pain are identifiable; minor gaps in urgency or evidence.
        9–12	Adequate	Problem exists but is vague or overly broad. Urgency unclear. Some ambiguity in who the customer is.
        5–8	Weak	Problem is implied but not articulated. Relies on assumptions. Missing market validation.
        1–4	Poor	Problem is barely mentioned, unclear, or unconvincing. Hard to tell why this needs solving.

        2. The Solution 20 Points

        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        17–20	Exceptional	Solution is crystal clear, differentiated, and defensible. Competitive moat is explicit (IP, network effects, proprietary data, etc.). Directly maps to the stated problem.
        13–16	Strong	Solution is clearly articulated. Competitive advantage is present but not fully fleshed out. Directly addresses the core problem.
        9–12	Adequate	Solution is present but vague or partially explained. Differentiation is implied but not proven. Some technical jargon without sufficient explanation.
        5–8	    Weak	Solution is hard to grasp or overly abstract. Competitive advantage unclear. Doesn't clearly connect back to the stated problem.
        1–4	Poor	Solution is missing, confusing, or appears easily replicable. No defensibility whatsoever.

        3. Founder–Market Fit 20 Points

        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        17–20	Exceptional	Team has deep, direct domain expertise. Unfair insight or access. Prior success in adjacent space. Complementary skillsets with no obvious gaps.
        13–16	Strong	Team is clearly qualified. Relevant experience demonstrated. Roles are complementary. Minor gaps acknowledged or addressed.
        9–12	Adequate	Team has some relevant experience but coverage is thin. Roles overlap or critical functions (e.g., tech, sales) are missing.
        5–8	    Weak	Team is present but lacks clear domain expertise. Background feels tangential to the problem being solved.
        1–4	    Poor	Team slide missing or lacks credibility. No apparent reason why this group is suited to solve this problem.

        4. Market Size & Dynamics 10 Points
        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        9–10	Exceptional	TAM/SAM/SOM clearly defined with credible sourcing. Market is growing. Competitive landscape is mapped (dense vs. fragmented).
        7–8	Strong	Market size is present and reasonable. Missing one of TAM/SAM/SOM or growth rate. Competition acknowledged.
        5–6	Adequate	Market size mentioned but not broken down. Single figure with limited sourcing. Competitive context missing.
        3–4	Weak	Market size vague or unsourced. No competitive landscape. Hard to assess attractiveness.
        1–2	Poor	Market slide absent or contains only generic claims without data.

        5. Business Model 10 Points
        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        9–10	Exceptional	Revenue model is clear, scalable, and margin-positive. Unit economics addressed. Pricing logic explained and defensible.
        7–8	Strong	Revenue streams are identifiable. Some margin logic present. Scalability implied but not fully quantified.
        5–6	Adequate	Business model is present but vague. Revenue source is implied. Margins and scalability not addressed.
        3–4	Weak	Business model is unclear or incomplete. No discussion of pricing, margin, or how the startup makes money.
        1–2	Poor	No business model presented or model is fundamentally flawed.

        6. Distribution / GTM Strategy 10 Points
        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        9–10	Exceptional	Clear first customer acquisition strategy. Defined wedge into the market. Unfair distribution advantage (existing network, partnerships, channel).
        7–8	Strong	GTM is described and logical. Customer acquisition path is believable. Some channel specificity.
        5–6	Adequate	GTM mentioned but generic. "We'll use social media and content marketing" without differentiation.
        3–4	Weak	GTM is an afterthought. No clear first customers or acquisition strategy articulated.
        1–2	Poor	No GTM strategy present. Assumes product will sell itself.

        7. Team Execution Capability 10 Points
        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        9–10	Exceptional	Roles are clearly defined and complementary. Prior execution track record. Advisors or investors lend credibility. Hiring plan aligns with use of funds.
        7–8	Strong	Team is capable and roles make sense. Some track record present. Minor gaps in coverage.
        5–6	Adequate	Team has potential but missing key roles. Advisors absent or irrelevant.
        3–4	Weak	Team roles are unclear or overlapping. No clear operator or business builder on the team.
        1–2	Poor	Team slide is absent or raises more questions than it answers.

        8. Traction & KPIs 5 Points

        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        5	Exceptional	KPIs are relevant, quantified, and show clear trajectory. Revenue, retention, or growth metrics present and trending positively.
        4	Strong	Some KPIs present. Metrics are directionally positive. Missing context on benchmarks or growth rate.
        3	Adequate	Traction mentioned but anecdotal. "We have 10 LOIs" without detail on conversion or size.
        2	Weak	Minimal traction signals. Mostly forward-looking without validation.
        1	Poor / N/A	No traction mentioned. Acceptable at pre-seed but must be acknowledged.

        9. Competitive Landscape 5 Points
        Scoring Criteria
        RANGE	TIER	DESCRIPTION
        5	Exceptional	Named competitors mapped clearly. Differentiation is explicit and credible. Shows awareness of why incumbents haven't solved this.
        4	Strong	Competition acknowledged with key differentiators stated. Missing one or two relevant players.
        3	Adequate	Competition generally acknowledged but not specifically named or analyzed.
        2	Weak	Only indirect competitors mentioned or competition is dismissed without reasoning.
        1	Poor	"We have no competition" — always a red flag.

        10. The Ask
        Scoring Criteria
        Clear, Funding amount is stated. Use of funds is broken down (product, hire, marketing). Milestones tied to the raise are explicit.
        Present, Amount is stated but use of funds is vague or generic.
        Absent, No ask slide. Investor must infer the round size.

        RED FLAGS
        •	No data or evidence backing the problem
        •	Problem is too broad or too niche to be actionable
        •	Assumes the problem without showing customer pain
        •	Technology exists but competitive moat is absent
        •	Solution solves a different problem than stated
        •	Easily copied by a well-resourced incumbent
        •	All founders are technical with no business/GTM lead (or vice versa)
        •	No direct domain experience
        •	Solo founder with no plan to hire key roles
        •	Claiming a massive TAM with no realistic path to capture any of it
        •	Ignoring well-funded incumbents
        •	Shrinking or commoditized market
        •	Race-to-the-bottom pricing with no path to margin
        •	Revenue model dependent on one large customer
        •	"We'll figure out monetization later"
        •	"Build it and they will come" mentality
        •	No identified design partners or pilot customers
        •	CAC/LTV not considered at all for B2B
        •	No operator or GTM-focused founder
        •	High team turnover history
        •	Equity split conflicts or missing co-founder agreements
        •	Vanity metrics with no business relevance (downloads ≠ users ≠ revenue)
        •	Traction plateau with no explanation
        •	Metrics that don't align with the stated business model
        •	"No competition" claim
        •	Ignoring well-funded direct competitors
        •	Competitive advantage that incumbents could replicate in 6 months
        •	Ask is disproportionate to stage or traction
        •	No milestone tied to the funding
        •	Use of funds is 90% salaries with no product investment

        
        1. For each of the 10 sections, determine if the startup actually addressed the topic (`is_present`).
        2. If present, assign a `score`. Be highly critical. Full points means it is top-tier Sequoia/Y-Combinator quality. Half points means it is average and needs work.
        3. Provide constructive `feedback` as if speaking to the founder. Point out exactly what is strong and what is dangerously vague.
        4. Quote the deck directly in the `evidence` field to justify your grade.
        5. If a section is entirely missing from the slides, set `is_present` to false, and leave the score, feedback, and evidence as `null`.

        Do not grade them on information that is not in the deck. If they forgot their Business Model, fail that section.
        """

    def _evaluate_uploaded_file(self, uploaded_file) -> PitchDeckEvaluation:
        prompt = self._evaluation_prompt()

        print("Evaluating deck...")
        
        # Pass the uploaded file and prompt to the LLM
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt], 
            config={
                "response_mime_type": "application/json",
                "response_schema": PitchDeckEvaluation,
                "temperature": 0.0 
            }
        )
        
        # Clean up the file from Google's servers
        if uploaded_file.name is not None:
            self.client.files.delete(name=uploaded_file.name)
        else:
            print("Skipping cleanup: uploaded file has no server-side name.")
        
        return PitchDeckEvaluation.model_validate(response.parsed)

    def extract_deck(self, pdf_path: str) -> Deck:
        """
        Extract structured metadata from a pitch deck.
        
        Args:
            pdf_path: Path to the PDF file to extract from.
            
        Returns:
            Deck: Structured deck object with title, company, team, stage, sector, and slides.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        print(f"Uploading {pdf_path} to Gemini for deck extraction...")
        uploaded_file = self.client.files.upload(file=pdf_path)

        prompt = """
        Extract only top-level deck metadata from this startup pitch deck.

        Return strictly valid JSON matching this schema:
        - title
        - company
        - team (list of names/roles)
        - stage
        - sector
        - slides (list of slide objects with: slide_number, title, text, graph_desc, section)

        If a field is missing, infer conservatively from the deck context.
        """

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": Deck,
                "temperature": 0.0,
            },
        )

        if uploaded_file.name is not None:
            self.client.files.delete(name=uploaded_file.name)

        deck = Deck.model_validate(response.parsed)
        print(f"Deck extracted: {deck.company}")
        return deck

    def calculate_fundability_score(self, evaluation: PitchDeckEvaluation) -> float:
        """
        Calculate a weighted fundability score out of 110 based on the Core 10 rubric.
        
        Missing sections (is_present=False) receive a 0 for that category.
        
        Args:
            evaluation: PitchDeckEvaluation object to score.
            
        Returns:
            float: Fundability score between 0 and 110.
        """
        # Define the weights (must sum to 1.0)
        sections = [
            "s1_problem",
            "s2_solution",
            "s3_market_size",
            "s4_product_and_tech",
            "s5_business_model",
            "s6_go_to_market",
            "s7_competition",
            "s8_team",
            "s9_traction_and_kpis",
            "s10_the_ask_and_financials",
        ]
    
        
        total_score = 0.0
        
        # Iterate through each of the Core 10 sections
        for section_name in sections:
            section_data = getattr(evaluation, section_name)
            
            # If the section is present and has a score, add to sum
            if type(section_data) == int:
                total_score +=  section_data
                
        return round(total_score, 2)

    def save_deck_to_json(self, deck: Deck, output_path: str = "deck.json") -> str:
        """
        Save extracted deck to a JSON file.
        
        Args:
            deck: Deck object to save.
            output_path: Path for the output JSON file.
            
        Returns:
            str: Path to the saved file.
        """
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(deck.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        print(f"Deck saved to {output_path}")
        return output_path

    def save_evaluation_to_json(self, evaluation: PitchDeckEvaluation, output_path: str = "evaluation.json") -> str:
        """
        Save evaluation results to a JSON file.
        
        Args:
            evaluation: PitchDeckEvaluation object to save.
            output_path: Path for the output JSON file.
            
        Returns:
            str: Path to the saved file.
        """
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(evaluation.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        print(f"Evaluation saved to {output_path}")
        return output_path

    def print_detailed_feedback(self, evaluation: PitchDeckEvaluation) -> None:
        """
        Print formatted detailed feedback from an evaluation.
        
        Args:
            evaluation: PitchDeckEvaluation object to print feedback for.
        """
        print("=" * 60)
        print(f"--- DETAILED FEEDBACK FOR: {evaluation.deck.company if evaluation.deck else 'Unknown Startup'} ---")
        print("=" * 60 + "\n")
        
        # Mapping of Pydantic attributes to readable headers
        core_10_sections = {
            "s1_problem": "1. Problem Statement",
            "s2_solution": "2. Solution & Value Prop",
            "s3_market_size": "3. Market Size (TAM)",
            "s4_product_and_tech": "4. Product & Technology",
            "s5_business_model": "5. Business Model",
            "s6_go_to_market": "6. Go-To-Market Strategy",
            "s7_competition": "7. Competition",
            "s8_team": "8. Team",
            "s9_traction_and_kpis": "9. Traction",
            "s10_the_ask_and_financials": "10. The Ask & Financials"
        }
        
        # Loop through the Core 10
        for attr_name, title in core_10_sections.items():
            section = getattr(evaluation, attr_name)
            
            print(title)
            if section.is_present:
                print(f"  Score:    {section.score}")
                print(f"  Feedback: {section.feedback}")
                print(f"  Evidence: \"{section.evidence}\"")
            else:
                print("  [!] MISSING: This section was not found in the deck.")
            print("-" * 50)
            
        # Print extracted KPIs
        print("\n" + "=" * 60)
        print("EXTRACTED INDUSTRY KPIs")
        print("=" * 60)
        if evaluation.extracted_kpis:
            for kpi in evaluation.extracted_kpis:
                print(f"  • {kpi.kpi_name}: {kpi.kpi_value}")
                print(f"    (Provenance: \"{kpi.provenance}\")")
        else:
            print("  No specific KPIs were explicitly stated.")

        # Print red flags
        print("\n" + "=" * 60)
        print("DETECTED RED FLAGS")
        print("=" * 60)
        if evaluation.red_flags:
            for flag in evaluation.red_flags:
                print(f"  [X] {flag}")
        else:
            print("  None detected. Looking good!")


class TestEval(unittest.TestCase):
    def testeval(self):
       parser = DeckParser()
       eval = parser.evaluate_pitch_deck("sample_startup_deck.pdf")
       parser.print_detailed_feedback(eval)
       
if __name__ == "__main__":
    unittest.main()
