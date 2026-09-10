from typing import List
from app.models.analysis import CandidateAnalysisResult, DecisionEnum


class CandidateRanker:
    @staticmethod
    def rank_candidates(analyses: List[CandidateAnalysisResult]) -> List[CandidateAnalysisResult]:
        """
        Sort candidate analysis results primarily by overall ATS score descending,
        with non-mandatory-failing candidates prioritized on score ties.
        """
        return sorted(
            analyses,
            key=lambda item: (
                not item.mandatory_failed,  # True (1) comes before False (0)
                item.score.overall,
                item.score.required_skills
            ),
            reverse=True
        )
