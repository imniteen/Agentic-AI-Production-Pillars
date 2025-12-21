from state import OverallState
import constants

def route_by_intent(state: OverallState) -> str | None:
    if state["intent"] == "faq":
        return constants.FAQ_AGENT
    elif state["intent"] == "order":
        return constants.ORDER_AGENT
    else:
        return constants.HUMAN_APPROVAL