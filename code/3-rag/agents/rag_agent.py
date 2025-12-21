import json
import logging
import os
from pathlib import Path
from langchain_core.runnables import RunnableConfig

from models.state import OverallState
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from opentelemetry import trace
from dotenv import load_dotenv

from langchain_pinecone import PineconeVectorStore

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("rag_agent")
logger.setLevel(logging.INFO)

load_dotenv(override=True)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "customer-service-rag")
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")

class RAGAgent:
    async def search(
            self,
            state: OverallState,
            callback_manager=None) -> OverallState:
        with tracer.start_as_current_span("rag_agent_reply") as span:
            span.set_attribute("run_id", state["run_id"])
            try:
                embeddings = OpenAIEmbeddings()
                vectorstore = PineconeVectorStore(index_name=PINECONE_INDEX, embedding=embeddings)
                retrieved_docs = vectorstore.similarity_search(query=state["user_message"], k=3)

                # Build structured retrieval records
                rag_contexts: list[str] = []
                rag_sources: list[dict] = []

                for idx, doc in enumerate(retrieved_docs):
                    meta = doc.metadata if hasattr(doc, 'metadata') else {}
                    source_name = meta.get(f"source", "unknown")
                    if source_name != "unknown":
                        source_name = Path(source_name).name
                    page = meta.get("page", "unknown")

                    rag_contexts.append(doc.page_content)
                    rag_sources.append(
                        {
                            "rank": idx + 1,
                            "source": source_name,
                            "page": page,
                            "metadata": meta,
                        }
                    )

                state["rag_contexts"] = rag_contexts
                state["rag_sources"] = rag_sources

                # Here, we only log a summarized view (source + page).
                summarized_sources = [
                    {"rank": r["rank"], "source": r["source"], "page": r["page"]}
                    for r in rag_sources
                ]
                span.set_attribute("rag.sources_summary", json.dumps(summarized_sources))
                context_str = "\n\n---\n\n".join(rag_contexts)

                rag_prompt = f"Answer the following question using only the provided context.\n\nContext:\n{context_str}\n\nQuestion: {state['user_message']}\nIf the answer is not in the context, strictly respond 'do not know'.\nAnswer: "

                rag_prompt_template = ChatPromptTemplate.from_messages([
                    SystemMessage(content=rag_prompt),
                    HumanMessage(content=state["user_message"]),
                ])
                # Pass callback_manager to LLM if supported
                chat_llm = ChatOpenAI() if callback_manager else ChatOpenAI()
                rag_chain = rag_prompt_template | chat_llm
                # Use only the propagated callback_manager
                run_metadata = {
                    "run_name": f"RAG Agent: Retrieval for '{state['user_message'][:40]}{'...' if len(state['user_message']) > 40 else ''}'",
                    "run_id": state["run_id"],
                    "agent_name": "RAG",
                    "user_message": state["user_message"],
                    "retrieved_sources": summarized_sources,
                    "timestamp": str(span.start_time) if hasattr(span, 'start_time') else None
                }
                result = await rag_chain.ainvoke({},
                                                 callbacks=callback_manager,
                                                 config=RunnableConfig(
                                                     metadata=run_metadata))
                span.set_attribute("rag.reply", result.content)
                source_citations = []
                for r in rag_sources:
                    if r["page"] != "unknown":
                        source_citations.append(
                            f"{r['rank']}: Document: {r['source']}, Page: {r['page']}"
                        )
                    else:
                        source_citations.append(
                            f"{r['rank']}: Document: {r['source']}"
                        )

                # Compose reply with answer, context, and citations
                reply_with_citations = (
                        f"Answer: {result.content}\n\n"
                        "Sources:\n" + "\n".join(source_citations)
                )
                state["citations"] = "\n".join(source_citations)
                state["draft_reply"] = reply_with_citations
                return state
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                logger.exception("Error in RAGAgent.search", exc_info=e)
                raise e
