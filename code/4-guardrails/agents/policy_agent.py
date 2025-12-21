import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from dotenv import load_dotenv
from opentelemetry import trace
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import SpacyRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from models.state import OverallState
from openai import OpenAI

load_dotenv(override=True)

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("policy_agent")
logger.setLevel(logging.INFO)

nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [
        {
            "lang_code": "en",
            "model_name": "en_core_web_sm",  # 👈 IMPORTANT
        }
    ],
}

provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
nlp_engine = provider.create_engine()

@dataclass
class PolicyDecision:
    allowed: bool
    action: str  # "allow" | "redact_and_allow" | "block_to_human" | "block"
    reason: str
    moderation_flagged: bool
    pii_entities: List[Dict[str, Any]]
    transformed_text: str


class PolicyAgent:
    """
    Production-grade baseline guardrails:
      - OpenAI Moderation API for toxicity/violence/self-harm/harassment categories
      - Presidio for PII detection + redaction
      - Writes structured decisions back to state for tracing + auditing
    """

    def __init__(
        self,
        moderation_model: str = "omni-moderation-latest",
        redact_pii: bool = True,
        on_input_flagged: str = "block_to_human",   # safer UX: escalate
        on_output_flagged: str = "block",           # replace with safe response
    ):
        self.chat_llm = OpenAI()
        self.moderation_model = moderation_model
        self.redact_pii = redact_pii
        self.on_input_flagged = on_input_flagged
        self.on_output_flagged = on_output_flagged

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

    def _moderate(self, text: str) -> Dict[str, Any]:
        response = self.chat_llm.moderations.create(model=self.moderation_model, input=text)
        result = response.results[0]
        return {
            "flagged": bool(getattr(result, "flagged", False)),
            "categories": getattr(result, "categories", None),
            "category_scores": getattr(result, "category_scores", None),
        }

    def _detect_pii(self, text: str, language: str = "en") -> List[Dict[str, Any]]:
        results = self.analyzer.analyze(text=text, language=language)
        return [
            {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": float(r.score)}
            for r in results
        ]

    def _redact(self, text: str) -> str:
        analysis = self.analyzer.analyze(text=text, language="en")
        operators = {"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})}
        return self.anonymizer.anonymize(text=text, analyzer_results=analysis, operators=operators).text

    def _decide(self, text: str, direction: str) -> PolicyDecision:
        
        pii = self._detect_pii(text)
        moderation = self._moderate(text)
        
        transformed = text
        action = "allow"
        reasons: List[str] = []

        if pii and self.redact_pii:
            transformed = self._redact(text)
            action = "redact_and_allow"
            reasons.append(f"PII detected ({len(pii)}) and redacted")

        
        if moderation["flagged"]:
            if direction == "input":
                action = self.on_input_flagged
                reasons.append("Moderation flagged user input")
                return PolicyDecision(
                    allowed=False,
                    action=action,
                    reason="; ".join(reasons),
                    moderation_flagged=True,
                    pii_entities=pii,
                    transformed_text="",
                )
            else:
                action = self.on_output_flagged
                reasons.append("Moderation flagged assistant output")
                return PolicyDecision(
                    allowed=False,
                    action=action,
                    reason="; ".join(reasons),
                    moderation_flagged=True,
                    pii_entities=pii,
                    transformed_text="",
                )

        return PolicyDecision(
            allowed=True,
            action=action,
            reason="; ".join(reasons) if reasons else "Allowed",
            moderation_flagged=False,
            pii_entities=pii,
            transformed_text=transformed
        )

    async def enforce_input(self, state: OverallState, callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("policy_agent_input") as span:
            span.set_attribute("run_id", state["run_id"])

            decision = self._decide(state["user_message"], direction="input")

            # Persist for audit/observability
            state["policy_input"] = asdict(decision)

            span.set_attribute("policy.input.action", decision.action)
            span.set_attribute("policy.input.allowed", decision.allowed)
            span.set_attribute("policy.input.pii_count", len(decision.pii_entities))
            span.set_attribute("policy.input.flagged", decision.moderation_flagged)

            if decision.allowed:
                # apply redaction if needed (so downstream agents never see raw PII)
                if decision.transformed_text and decision.transformed_text != state["user_message"]:
                    state["user_message"] = decision.transformed_text
                state["policy_route"] = "continue"
                return state

            # If blocked: route to human with a reason (triage shouldn’t see unsafe content)
            state["policy_route"] = {"route": "human", "reason": decision.reason}
            return state

    async def enforce_output(self, state: OverallState, callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("policy_agent_output") as span:
            span.set_attribute("run_id", state["run_id"])

            # Prefer final_reply if ToneAgent sets it; otherwise fall back to draft_reply.
            text = state.get("draft_reply") or state.get("user_message", "")
            decision = self._decide(text, direction="output")

            state["policy_output"] = asdict(decision)

            span.set_attribute("policy.output.action", decision.action)
            span.set_attribute("policy.output.allowed", decision.allowed)
            span.set_attribute("policy.output.pii_count", len(decision.pii_entities))
            span.set_attribute("policy.output.flagged", decision.moderation_flagged)

            if decision.allowed:
                if decision.transformed_text and decision.transformed_text != text:
                    # redact PII in the outgoing response
                    state["draft_reply"] = decision.transformed_text
                return state

            # Unsafe output: replace with safe response (don’t leak)
            safe = "Detected unsafe content to output by policy and guardrails"
            state["draft_reply"] = safe
            return state
