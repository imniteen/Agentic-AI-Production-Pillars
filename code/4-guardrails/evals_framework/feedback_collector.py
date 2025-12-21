import os
from datetime import datetime
from langsmith import Client
LANGSMITH_PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "Customer Service Agent")

class FeedbackCollector:
    def __init__(self):
        self.client = Client()

    def add_thumbs_feedback(
            self,
            run_id: str,
            is_positive_feedback: bool,
            comment: str = ""):
        """
        Strategy 1: Simple thumbs up/down feedback with rich metadata
        """
        try:
            key = "user.thumbs_up" if is_positive_feedback else "user.thumbs_down"
            self.client.create_feedback(
                run_id=str(run_id),
                key=key,
                score=1.0 if is_positive_feedback else 0.0,
                comment=comment
            )
        except Exception as e:
            raise e

    def add_rating_feedback(self, run_id: str, rating: int, max_rating: int = 5, user_message: str = None, agent_type: str = None, metadata: dict = None):
        """
        Strategy 2: Star rating (1-5 stars) with rich metadata
        """
        normalized_score = rating / max_rating
        feedback_metadata = metadata or {}
        feedback_metadata.update({
            "user_message": user_message,
            "agent_type": agent_type,
            "feedback_type": "star_rating",
            "timestamp": datetime.utcnow().isoformat()
        })
        self.client.create_feedback(
            run_id=run_id,
            key="star_rating",
            score=normalized_score,
            value=str(rating),
            comment=f"{rating}/{max_rating} stars",
            metadata=feedback_metadata
        )

    def add_expert_correction(self, run_id: str, corrected_answer: str, expert_id: str, user_message: str = None, agent_type: str = None, metadata: dict = None):
        """
        Strategy 3: Expert provides corrected/ideal answer (becomes ground truth) with metadata
        """
        feedback_metadata = metadata or {}
        feedback_metadata.update({
            "user_message": user_message,
            "agent_type": agent_type,
            "feedback_type": "expert_correction",
            "expert_id": expert_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.client.create_feedback(
            run_id=run_id,
            key="expert_correction",
            score=0.0,  # 0 means original was incorrect
            value=corrected_answer,
            comment=f"Corrected by expert: {expert_id}",
            metadata=feedback_metadata
        )

    def add_user_verified_answer(self, run_id: str, is_correct: bool, ground_truth: str = None, user_message: str = None, agent_type: str = None, metadata: dict = None):
        """
        Strategy 4: User verifies if answer is correct and optionally provides ground truth, with metadata
        """
        feedback_metadata = metadata or {}
        feedback_metadata.update({
            "user_message": user_message,
            "agent_type": agent_type,
            "feedback_type": "user_verification",
            "timestamp": datetime.utcnow().isoformat()
        })
        self.client.create_feedback(
            run_id=run_id,
            key="user_verification",
            score=1.0 if is_correct else 0.0,
            value=ground_truth,
            comment="User verified answer correctness",
            metadata=feedback_metadata
        )

    def add_implicit_feedback(self, run_id: str, user_action: str, engagement_score: float, user_message: str = None, agent_type: str = None, metadata: dict = None):
        """
        Strategy 5: Implicit feedback from user behavior with metadata
        Examples: click-through rate, time spent, copied answer, etc.
        """
        feedback_metadata = metadata or {}
        feedback_metadata.update({
            "user_message": user_message,
            "agent_type": agent_type,
            "feedback_type": "implicit_engagement",
            "user_action": user_action,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.client.create_feedback(
            run_id=run_id,
            key="implicit_engagement",
            score=engagement_score,
            comment=f"User action: {user_action}",
            metadata=feedback_metadata
        )