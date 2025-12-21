import os
from datetime import datetime, timedelta, timezone
from langsmith import Client
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")


class DynamicDatasetBuilder:
    """
    Builds evaluation datasets from production traffic.
    No upfront data needed - uses real user interactions.
    """

    def __init__(self, project_name: str = LANGSMITH_PROJECT_NAME):
        self.client = Client()
        self.project_name = project_name

    def create_dataset_from_production(
            self,
            dataset_name: str = "customer-service-rag-production-dataset",
            hours_lookback: int = 24,
            max_examples: int = 100
    ) -> None:
        """
        Strategy 1: Create dataset from high-quality production runs
        Uses runs with good user feedback as golden examples
        """
        start_time = datetime.now() - timedelta(hours=hours_lookback)

        # Fetch production runs
        quality_runs = list(self.client.list_runs(
            project_name=self.project_name,
            start_time=start_time,
            is_root=True
        ))

        # Create dataset with a descriptive name/description
        try:
            dataset = None
            if not self.client.has_dataset(dataset_name=dataset_name):
                dataset = self.client.create_dataset(
                    dataset_name=dataset_name,
                    description=f"Production RAG dataset with rich context and feedback (last {hours_lookback}h, created {datetime.now().isoformat()})"
                )
            else:
                dataset = self.client.read_dataset(dataset_name=dataset_name)

            # Remove the runs which is already part of the dataset
            existing_examples = list(self.client.list_examples(dataset_id=dataset.id))
            existing_run_ids = {example.source_run_id for example in existing_examples if example.source_run_id}
            quality_runs = [run for run in quality_runs if run.id not in existing_run_ids]

            # Add examples from quality runs
            added = 0
            for run in quality_runs[:max_examples]:
                if run.inputs and run.outputs:
                    # --- Fetch child runs and augment outputs with rag context ---
                    user_message = run.inputs.get("user_message") if hasattr(run, "inputs") else None
                    child_runs = list(self.client.list_runs(parent_run_id=run.id))
                    for child in child_runs:
                        agent_name = child.name
                        is_rag = 'rag' in child.name.lower() if child.name else ""
                        if is_rag: # Only consider RAG-related child runs
                            rag_contexts = child.outputs.get("rag_contexts") if child.outputs else None
                            rag_sources = child.outputs.get("rag_sources") if child.outputs else None
                            # If not in outputs, check extra/state
                            if not rag_contexts and hasattr(child, "extra"):
                                rag_contexts = child.extra.get("rag_contexts")
                            if not rag_sources and hasattr(child, "extra"):
                                rag_sources = child.extra.get("rag_sources")

                            # Augment outputs
                            outputs = dict(run.outputs)
                            if rag_contexts:
                                outputs["rag_contexts"] = rag_contexts
                            if rag_sources:
                                outputs["rag_sources"] = rag_sources
                            # Compose rich metadata for the example
                            example_metadata = {
                                "source": "production",
                                "run_id": str(run.id),
                                "timestamp": run.start_time.isoformat() if run.start_time else datetime.now().isoformat(),
                                "user_message": user_message,
                                "agent_name": agent_name or "",
                                "retrieved_sources": rag_sources,
                                "feedback_type": "user_feedback"
                            }
                            self.client.create_example(
                                dataset_id=dataset.id,
                                inputs=run.inputs,
                                outputs=outputs,
                                source_run_id=run.id,
                                metadata=example_metadata
                            )
                            added += 1

            print(f"✅ Refreshed dataset '{dataset_name}' with {added} examples from production")

        except Exception as e:
            raise e

    def create_dataset_from_expert_corrections(
            self,
            dataset_name: str,
            hours_lookback: int = 168  # 1 week
    ) -> str:
        """
        Strategy 2: Create dataset from expert-corrected answers
        These become ground truth examples
        """

        start_time = datetime.utcnow() - timedelta(hours=hours_lookback)

        # Fetch runs with expert corrections
        runs = list(self.client.list_runs(
            project_name=self.project_name,
            start_time=start_time
        ))

        expert_corrected = []
        for run in runs:
            feedback_list = list(self.client.list_feedback(run_ids=[run.id]))

            for feedback in feedback_list:
                if feedback.key == "expert_correction" and feedback.value:
                    expert_corrected.append({
                        "run": run,
                        "ground_truth": feedback.value,
                        "expert_comment": feedback.comment
                    })

        # Create dataset
        try:
            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description="Dataset from expert corrections"
            )

            for item in expert_corrected:
                self.client.create_example(
                    dataset_id=dataset.id,
                    inputs=item["run"].inputs,
                    outputs={"ground_truth": item["ground_truth"]},
                    metadata={
                        "source": "expert_correction",
                        "comment": item["expert_comment"]
                    }
                )

            print(f"✅ Refreshed dataset with {len(expert_corrected)} expert-corrected examples")
            return dataset.id

        except Exception as e:
            print(f"Error creating dataset: {e}")
            return None

    def create_dataset_from_failed_runs(
            self,
            dataset_name: str,
            hours_lookback: int = 24,
            max_feedback_score: float = 0.3
    ) -> str:
        """
        Strategy 3: Create dataset from failed/poor runs for improvement
        """

        start_time = datetime.utcnow() - timedelta(hours=hours_lookback)

        runs = list(self.client.list_runs(
            project_name=self.project_name,
            start_time=start_time
        ))

        poor_runs = []
        for run in runs:
            feedback_list = list(self.client.list_feedback(run_ids=[run.id]))

            if feedback_list:
                avg_score = sum(f.score for f in feedback_list if f.score) / len(feedback_list)
                if avg_score <= max_feedback_score:
                    poor_runs.append(run)

        try:
            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description="Failed runs needing improvement"
            )

            for run in poor_runs:
                self.client.create_example(
                    dataset_id=dataset.id,
                    inputs=run.inputs,
                    outputs=run.outputs,
                    metadata={"source": "failed_run", "needs_improvement": True}
                )

            print(f"✅ Created dataset with {len(poor_runs)} failed examples")
            return dataset.id

        except Exception as e:
            print(f"Error: {e}")
            return None