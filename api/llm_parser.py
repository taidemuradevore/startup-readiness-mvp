import unittest

from google import genai
import html
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Optional, List, Union, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv


# ==================== PYDANTIC MODELS ====================

class GradedSection(BaseModel):
    is_present: bool = Field(
        description="True if this topic is addressed anywhere in the deck. False if completely missing."
    )
    score: Optional[Union[int, float, str]] = Field(
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
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Evaluator confidence from 0 to 1, based on evidence quality and verifiability."
    )
    adjusted_score: Optional[float] = Field(
        default=None,
        description="Confidence-adjusted score on the same point scale as score."
    )
    confidence_reason: Optional[str] = Field(
        default=None,
        description="Short reason for the confidence value."
    )
    verification_status: Optional[str] = Field(
        default=None,
        description="External verification status for claims that affected this rubric section."
    )
    critic_notes: Optional[str] = Field(
        default=None,
        description="Critic pass notes explaining score or confidence revisions."
    )
    external_checks: list["ExternalCheckResult"] = Field(
        default_factory=list,
        description="External checks used to validate claims relevant to this section."
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


class ExternalCheckResult(BaseModel):
    claim: str = Field(description="The deck claim or query being checked.")
    source: str = Field(description="Verifier source, such as web_search or internal.")
    status: Literal["verified", "unverified", "contradicted", "unavailable"] = Field(
        description="Verification outcome."
    )
    summary: str = Field(description="Brief explanation of what was found.")
    url: Optional[str] = Field(default=None, description="Best source URL, if available.")


GradedSection.model_rebuild()


class RubricSubagentDraft(BaseModel):
    is_present: bool
    score: Optional[Union[int, float, str]] = None
    feedback: Optional[str] = None
    evidence: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reason: str
    requested_external_checks: list[str] = Field(default_factory=list)


class RubricCritique(BaseModel):
    concerns: list[str] = Field(default_factory=list)
    score_adjustment: Optional[float] = Field(
        default=None,
        description="Suggested final numeric score on this section's point scale, if the draft should change."
    )
    confidence_adjustment: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Suggested final confidence from 0 to 1, if the draft should change."
    )
    needs_external_verification: bool = False
    external_check_queries: list[str] = Field(default_factory=list)
    notes: str


class RubricFinalGrade(BaseModel):
    is_present: bool
    score: Optional[Union[int, float, str]] = None
    adjusted_score: Optional[float] = None
    feedback: Optional[str] = None
    evidence: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reason: str
    verification_status: Literal["verified", "unverified", "contradicted", "unavailable", "not_needed"]
    critic_notes: str
    external_checks: list[ExternalCheckResult] = Field(default_factory=list)


class EvaluationExtras(BaseModel):
    extracted_kpis: list[KPIMetric] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    final_grade: Optional[str] = None


RUBRIC_SECTIONS = [
    {
        "attr": "s1_problem",
        "title": "Problem",
        "max_points": 20,
        "rubric": "Grade whether the problem is acute, clearly defined, quantified, and validated by customer pain.",
    },
    {
        "attr": "s2_solution",
        "title": "Solution",
        "max_points": 20,
        "rubric": "Grade whether the solution directly solves the problem, is clear, differentiated, and defensible.",
    },
    {
        "attr": "s3_market_size",
        "title": "Market Size",
        "max_points": 10,
        "rubric": "Grade TAM/SAM/SOM logic, market growth, and credibility of sources.",
    },
    {
        "attr": "s4_product_and_tech",
        "title": "Product & Tech",
        "max_points": 5,
        "rubric": "Grade the product depth, technical magic, IP, proprietary data, and feasibility. This section is capped at 5 so team credibility carries more weight.",
    },
    {
        "attr": "s5_business_model",
        "title": "Business Model",
        "max_points": 10,
        "rubric": "Grade revenue model clarity, pricing, margin logic, unit economics, and scalability.",
    },
    {
        "attr": "s6_go_to_market",
        "title": "Go-To-Market",
        "max_points": 10,
        "rubric": "Grade first customer acquisition strategy, wedge, channels, partnerships, and distribution advantage.",
    },
    {
        "attr": "s7_competition",
        "title": "Competition",
        "max_points": 5,
        "rubric": "Grade competitor awareness, specific rivals, differentiation, and defensibility against incumbents.",
    },
    {
        "attr": "s8_team",
        "title": "Team",
        "max_points": 20,
        "rubric": "Grade founder-market fit, domain expertise, operating credibility, technical/GTM coverage, prior execution, advisors, and claim verifiability. Be strict: team quality and credibility are a core investment driver.",
    },
    {
        "attr": "s9_traction_and_kpis",
        "title": "Traction & KPIs",
        "max_points": 5,
        "rubric": "Grade revenue, pilots, retention, usage growth, LOIs, KPI relevance, and trajectory.",
    },
    {
        "attr": "s10_the_ask_and_financials",
        "title": "The Ask & Financials",
        "max_points": 5,
        "rubric": "Grade whether raise amount, use of funds, milestones, and projections are explicit and realistic.",
    },
]


class ExternalVerifier:
    """Best-effort verifier with a pluggable interface and public web fallback."""

    def verify_team_and_company(self, deck: Deck) -> list[ExternalCheckResult]:
        claims = []
        if deck.company:
            claims.append(f"{deck.company} startup company")
        for team_member in deck.team:
            if team_member:
                claims.append(f"{team_member} {deck.company} founder background")
        return self.verify_claims(claims)

    def verify_claims(self, claims: list[str]) -> list[ExternalCheckResult]:
        results = []
        seen = set()
        for claim in claims:
            normalized_claim = re.sub(r"\s+", " ", str(claim)).strip()
            if not normalized_claim or normalized_claim.lower() in seen:
                continue
            seen.add(normalized_claim.lower())
            results.append(self._verify_with_web_search(normalized_claim))
            if len(results) >= 8:
                break
        return results

    def _verify_with_web_search(self, claim: str) -> ExternalCheckResult:
        query = urllib.parse.urlencode({"q": claim})
        url = f"https://duckduckgo.com/html/?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "startup-readiness-verifier/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read(120000).decode("utf-8", errors="ignore")
        except Exception as exc:
            return ExternalCheckResult(
                claim=claim,
                source="web_search",
                status="unavailable",
                summary=f"External web search unavailable: {exc}",
                url=None,
            )

        text = html.unescape(re.sub(r"<[^>]+>", " ", body))
        normalized_text = re.sub(r"\s+", " ", text).strip()
        tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", claim) if len(token) > 2]
        hits = sum(1 for token in tokens if token in normalized_text.lower())
        first_link = self._first_result_url(body)
        status = "verified" if tokens and hits >= max(2, len(tokens) // 2) else "unverified"
        summary = normalized_text[:320] if normalized_text else "Search returned no usable text."
        return ExternalCheckResult(
            claim=claim,
            source="web_search",
            status=status,
            summary=summary,
            url=first_link,
        )

    def _first_result_url(self, body: str) -> Optional[str]:
        match = re.search(r'class="result__a" href="([^"]+)"', body)
        if not match:
            return None
        href = html.unescape(match.group(1))
        parsed = urllib.parse.urlparse(href)
        if parsed.query:
            query = urllib.parse.parse_qs(parsed.query)
            uddg = query.get("uddg")
            if uddg:
                return uddg[0]
        return href


class DeckEvaluationOrchestrator:
    def __init__(self, client):
        self.client = client
        self.verifier = ExternalVerifier()

    def evaluate_uploaded_file(self, uploaded_file) -> PitchDeckEvaluation:
        deck = self._extract_deck(uploaded_file)
        mandatory_checks = self.verifier.verify_team_and_company(deck)
        final_sections: dict[str, GradedSection] = {}

        for section in RUBRIC_SECTIONS:
            checks = list(mandatory_checks) if section["attr"] == "s8_team" else []
            draft = self._run_subagent(uploaded_file, deck, section, checks)
            requested_checks = self.verifier.verify_claims(draft.requested_external_checks)
            checks.extend(requested_checks)
            critique = self._run_critic(uploaded_file, deck, section, draft, checks)
            if critique.needs_external_verification:
                checks.extend(self.verifier.verify_claims(critique.external_check_queries))
            final_grade = self._run_final_grader(uploaded_file, deck, section, draft, critique, checks)
            final_sections[section["attr"]] = self._section_from_final(section, final_grade)

        extras = self._extract_extras(uploaded_file, deck, final_sections)
        return PitchDeckEvaluation(
            deck=deck,
            extracted_kpis=extras.extracted_kpis,
            red_flags=extras.red_flags,
            final_grade=extras.final_grade,
            **final_sections,
        )

    def _extract_deck(self, uploaded_file) -> Deck:
        prompt = """
        Extract structured deck metadata and slide text from this startup pitch deck.
        Include every slide you can read. Infer missing top-level metadata conservatively.
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
        return Deck.model_validate(response.parsed)

    def _run_subagent(
        self,
        uploaded_file,
        deck: Deck,
        section: dict,
        external_checks: list[ExternalCheckResult],
    ) -> RubricSubagentDraft:
        prompt = f"""
        You are the specialist subagent for the rubric item: {section['title']}.
        Max points: {section['max_points']}.
        Rubric: {section['rubric']}

        Deck metadata:
        {deck.model_dump_json()}

        External checks available:
        {json.dumps([check.model_dump(mode="json") for check in external_checks], ensure_ascii=False)}

        Return a structured draft grade only for this rubric item. Use direct deck evidence.
        Confidence must reflect evidence quality and verifiability. If you need external checks for non-team claims,
        list concise search queries in requested_external_checks.
        """
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": RubricSubagentDraft,
                "temperature": 0.0,
            },
        )
        return RubricSubagentDraft.model_validate(response.parsed)

    def _run_critic(
        self,
        uploaded_file,
        deck: Deck,
        section: dict,
        draft: RubricSubagentDraft,
        external_checks: list[ExternalCheckResult],
    ) -> RubricCritique:
        prompt = f"""
        You are the critic for a VC deck evaluation subagent.
        Rubric item: {section['title']} / {section['max_points']} points.
        Rubric: {section['rubric']}

        Draft:
        {draft.model_dump_json()}

        Deck metadata:
        {deck.model_dump_json()}

        External checks:
        {json.dumps([check.model_dump(mode="json") for check in external_checks], ensure_ascii=False)}

        Find overclaims, missing deck evidence, score inflation, and confidence problems.
        Return exactly one critique pass. For Team, be especially strict about credibility and founder-market fit.
        """
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": RubricCritique,
                "temperature": 0.0,
            },
        )
        return RubricCritique.model_validate(response.parsed)

    def _run_final_grader(
        self,
        uploaded_file,
        deck: Deck,
        section: dict,
        draft: RubricSubagentDraft,
        critique: RubricCritique,
        external_checks: list[ExternalCheckResult],
    ) -> RubricFinalGrade:
        prompt = f"""
        Produce the final structured grade for {section['title']}.
        Max points: {section['max_points']}.
        Rubric: {section['rubric']}

        Draft:
        {draft.model_dump_json()}

        Critique:
        {critique.model_dump_json()}

        Deck metadata:
        {deck.model_dump_json()}

        External checks:
        {json.dumps([check.model_dump(mode="json") for check in external_checks], ensure_ascii=False)}

        Rules:
        - Clamp score between 0 and {section['max_points']}.
        - Confidence is 0 to 1 and should fall when evidence is thin or external checks are unavailable.
        - adjusted_score is score * confidence, rounded to one decimal.
        - Do not give credit for facts absent from the deck, except verified credibility can affect confidence.
        - For Team, value quality and credibility highly, and penalize unverifiable exceptional claims softly.
        """
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": RubricFinalGrade,
                "temperature": 0.0,
            },
        )
        return RubricFinalGrade.model_validate(response.parsed)

    def _extract_extras(
        self,
        uploaded_file,
        deck: Deck,
        sections: dict[str, GradedSection],
    ) -> EvaluationExtras:
        prompt = f"""
        Extract hard KPIs, red flags, and an overall letter grade from this pitch deck and the structured rubric results.

        Deck metadata:
        {deck.model_dump_json()}

        Rubric results:
        {json.dumps({key: value.model_dump(mode="json") for key, value in sections.items()}, ensure_ascii=False)}

        Red flags should focus on investor-relevant risks, including team credibility gaps, unverifiable claims,
        missing business model, weak GTM, weak traction, unrealistic market sizing, and unsupported technical moats.
        """
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config={
                "response_mime_type": "application/json",
                "response_schema": EvaluationExtras,
                "temperature": 0.0,
            },
        )
        return EvaluationExtras.model_validate(response.parsed)

    def _section_from_final(self, section: dict, final_grade: RubricFinalGrade) -> GradedSection:
        raw_score = self._coerce_score(final_grade.score)
        confidence = self._clamp(final_grade.confidence, 0.0, 1.0)
        if raw_score is not None:
            raw_score = self._clamp(raw_score, 0.0, float(section["max_points"]))
        adjusted_score = final_grade.adjusted_score
        if adjusted_score is None and raw_score is not None:
            adjusted_score = round(raw_score * confidence, 1)
        if adjusted_score is not None:
            adjusted_score = round(self._clamp(float(adjusted_score), 0.0, float(section["max_points"])), 1)

        return GradedSection(
            is_present=final_grade.is_present,
            score=round(raw_score, 1) if raw_score is not None else final_grade.score,
            feedback=final_grade.feedback,
            evidence=final_grade.evidence,
            confidence=round(confidence, 2),
            adjusted_score=adjusted_score,
            confidence_reason=final_grade.confidence_reason,
            verification_status=final_grade.verification_status,
            critic_notes=final_grade.critic_notes,
            external_checks=final_grade.external_checks,
        )

    def _coerce_score(self, value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None

    def _clamp(self, value: float, low: float, high: float) -> float:
        return min(high, max(low, value))


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
        try:
            if os.getenv("USE_ORCHESTRATED_EVALUATOR", "true").lower() != "false":
                print("Evaluating deck with orchestrated rubric subagents...")
                return DeckEvaluationOrchestrator(self.client).evaluate_uploaded_file(uploaded_file)
            return self._legacy_evaluate_uploaded_file(uploaded_file)
        finally:
            if uploaded_file.name is not None:
                self.client.files.delete(name=uploaded_file.name)
            else:
                print("Skipping cleanup: uploaded file has no server-side name.")

    def _legacy_evaluate_uploaded_file(self, uploaded_file) -> PitchDeckEvaluation:
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
