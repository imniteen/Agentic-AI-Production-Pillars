import os
from typing import List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithoutReference, \
    ResponseGroundedness, ContextRelevance
from ragas import evaluate as ragas_evaluate, SingleTurnSample, EvaluationDataset
from langsmith import Client

load_dotenv(override=True)

LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")


class ContinuousEvaluator:
    """
    Continuously evaluates production traffic without needing upfront datasets.
    Uses sampling and asynchronous evaluation.
    """

    def __init__(self, project_name: str = LANGSMITH_PROJECT_NAME):
        self.client = Client()
        self.project_name = project_name
        # Choose *reference-free* metrics for production traces
        self.metrics = [
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithoutReference(),
            ResponseGroundedness(),
            ContextRelevance()
        ]

    def evaluate_production_sample(
            self,
            hours_lookback: int = 24
    ):
        """
        Evaluate a sample of recent production runs using Ragas.
        No ground truth needed for metrics like faithfulness and relevancy.
        """
        try:
            print(f"📊 Evaluating last {hours_lookback} hours of production data...")
            eval_dataset = list(self.client.list_datasets())[
                0]  # Assuming dataset is already created, pick the first one for simplicity

            if eval_dataset is None:
                return {"error": "No evaluation dataset found. Please create one using DynamicDatasetBuilder."}

            # Get examples for that dataset
            examples = list(self.client.list_examples(dataset_id=eval_dataset.id))

            samples: List[SingleTurnSample] = []
            run_ids = []
            for example in examples:
                user_input = (example.inputs.get("user_message", "")
                              or example.inputs.get("query", "")
                              or example.inputs.get("question", ""))
                response = example.outputs["final_reply"]
                retrieved_contexts = example.outputs.get("rag_contexts", [])

                samples.append(SingleTurnSample(
                    user_input=user_input,
                    response=response,
                    retrieved_contexts=retrieved_contexts
                ))
                run_ids.append(example.source_run_id)

            eval_dataset = EvaluationDataset(samples=samples)

            # Configure Ragas
            evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

            # Evaluate
            result = ragas_evaluate(dataset=eval_dataset, metrics=self.metrics, llm=evaluator_llm)
            self._push_scores_to_langsmith(result=result, run_ids=run_ids)
        except Exception as e:
            raise e

    def _push_scores_to_langsmith(
            self,
            result,
            run_ids: List[str],
    ):
        """
        Map per-sample scores back to the corresponding LangSmith runs
        via Client.create_feedback.
        """

        df = result.to_pandas()  # merges dataset + scores columns

        metric_names = [m.name for m in self.metrics]  # e.g. "faithfulness", "response_relevancy"

        for idx, row in df.iterrows():
            if idx >= len(run_ids):
                break
            run_id = run_ids[idx]

            for metric_name in metric_names:
                if metric_name not in row or row[metric_name] is None:
                    continue
                score = float(row[metric_name])

                # Attach as feedback to the *same* root run in LangSmith
                # Signature from official Client docs.
                self.client.create_feedback(
                    run_id=run_id,
                    key=f"ragas.{metric_name}",
                    score=score
                )
