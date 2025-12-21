from state import OverallState
import constants

def route_by_intent(state: OverallState) -> str | None:
    if state["intent"] == "order":
        return constants.ORDER_AGENT
    elif state["intent"] == "faq":
        return constants.FAQ_AGENT
    elif state["intent"] == "chit-chat":
        return constants.TONE_AGENT
    else:
        return constants.HUMAN

def route_by_faq(state: OverallState) -> str | None:
    if state["intent"] == "rag":
        return constants.RAG_AGENT
    else:
        return constants.TONE_AGENT
