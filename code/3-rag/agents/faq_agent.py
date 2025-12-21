import os
from datetime import datetime
from uuid import UUID

from langchain_core.callbacks import CallbackManager
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers import LangChainTracer

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import logging
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("faq_agent")
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")


class FAQAgent:
    def __init__(self):
        self.chat_llm = ChatOpenAI()
        self.faq_prompt = """
            You are the FAQ Agent for an e-commerce customer service system.
            You have TWO responsibilities:
            1. Decide whether the user's question:
               a) Can be answered safely from generic e-commerce knowledge, OR
               b) Requires COMPANY-SPECIFIC information from our internal knowledge bases
                  (policies, FAQs, runbooks, SOPs, legal terms, pricing rules, etc.)
            2. Based on that decision:
               - EITHER answer directly using your general e-commerce knowledge,
               - OR explicitly call the RAG Agent to fetch and ground the answer in our
                 company documentation.
            
            IMPORTANT:
            - If you are even slightly uncertain whether the answer is company-specific, ALWAYS respond with 'rag'.
            - NEVER guess or invent any company-specific information, numbers, or policies.
            - If answering directly, DO NOT mention the company, brand, or website. Speak in general terms only.
            
            --------------------------------
            WHEN TO CALL THE RAG AGENT
            --------------------------------
            Call the RAG Agent whenever the question depends on details that are:
            - Specific to our company, brand, or website
            - Policy / legal / contractual / compliance-related
            - Money-related or high-risk if answered incorrectly
            - Operational and likely to change over time
            
            Typical examples that SHOULD go to the RAG Agent:
            - “What is your return or refund policy for international orders?”
            - “How long do I have to return a sale item?”
            - “Is shipping free for orders above ₹2000 / $50?”
            - “What is your warranty coverage for electronics?”
            - “How do I use my store credit or loyalty points?”
            - “Do you ship to Canada? What are the duties or taxes?”
            - “Can I change my address after placing an order?”
            - “What is your privacy policy for my data?”
            - “What happens if my order arrives damaged?”
            - “How do cancellations work once the order is shipped?”
            - Any question that mentions: ‘your website’, ‘your policy’, ‘your store’,
              ‘your app’, specific plans, tiers, promotions, coupons, membership, etc.
            
            In these cases, DO NOT invent or guess policy details.
            Instead, call the RAG Agent so it can retrieve the relevant internal docs.
            
            --------------------------------
            WHEN TO ANSWER DIRECTLY (NO RAG)
            --------------------------------
            Answer directly using your general e-commerce knowledge when the question is:
            - Generic to online shopping, not specific to our brand
            - Educational or conceptual
            - About best practices or how things usually work in e-commerce
            - Not about our specific policies, terms, or numbers
            
            Typical examples that you MAY answer directly:
            - “What does Cash on Delivery mean?”
            - “What is a tracking number?”
            - “What is the difference between ‘Processing’ and ‘Shipped’ status in general?”
            - “How should I choose the right clothing size when shopping online?”
            - “What should I do if my parcel is late in general?”
            - “What is two-factor authentication at login?”
            - “What are common payment methods in e-commerce?”
            
            In direct answers:
            - Speak generally (e.g., “In most online stores…”).
            - DO NOT state specific numbers, time windows, or guarantees
              as if they are our official policy.
            
            --------------------------------
            OUTPUT FORMAT
            --------------------------------
            You must output ONLY one of the following:
            - The word 'rag' (if the RAG Agent should be called),
            - If you can answer directly, provide a concise answer based on general e-commerce knowledge.
            - The phrase 'do not know' (if you cannot answer).
            Do NOT include any explanations, reasoning, or extra text.
        """

    async def reply(
            self,
            state: OverallState,
            callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("faq_agent_reply") as span:
            span.set_attribute("run_id", state["run_id"])
            faq_prompt_template = ChatPromptTemplate.from_messages([
                SystemMessage(content=self.faq_prompt),
                HumanMessage(content=state["user_message"]),
            ])
            try:
                faq_prompt_chain = faq_prompt_template | self.chat_llm
                tracer_instance = LangChainTracer(project_name=LANGSMITH_PROJECT_NAME)
                # Use provided callback_manager if available
                callback_manager = callback_manager if callback_manager else CallbackManager([tracer_instance])
                run_metadata = {
                    "run_name": f"FAQ Agent: FAQ Handling for '{state['user_message'][:40]}{'...' if len(state['user_message']) > 40 else ''}'",
                    "run_id": state["run_id"],
                    "agent_name": "FAQ",
                    "user_message": state["user_message"],
                    "timestamp": str(span.start_time) if hasattr(span, 'start_time') else datetime.now().isoformat()
                }
                result = await faq_prompt_chain.ainvoke({},
                                                        callbacks=callback_manager,
                                                        config=RunnableConfig(
                                                            metadata=run_metadata))
                span.set_attribute("order.reply", result.content)
                response = result.content.strip()
                if "rag" in response.lower():
                    state["intent"] = "rag"
                    return state
                else:
                    state["draft_reply"] = response
                    return state
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise e
