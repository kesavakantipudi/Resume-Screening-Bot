import pytest
from app.models.job import JobDescriptionData
from app.models.candidate import CandidateData, EducationItem
from app.models.analysis import DecisionEnum
from app.recruitment.matcher import MatchAnalysisSchema, EvaluationSchema
from app.recruitment.scorer import ATSScorer


def test_scorer_high_match():
    job = JobDescriptionData(
        job_title="Python AI Engineer",
        required_skills=["Python", "FastAPI", "SQL", "Machine Learning"],
        preferred_skills=["Docker", "AWS"],
        required_experience_years=2.0,
        education_requirements=["B.Tech"]
    )

    candidate = CandidateData(
        candidate_name="John Doe",
        skills=["Python", "FastAPI", "SQL", "Machine Learning", "Docker", "AWS"],
        total_experience_years=3.5,
        education=[EducationItem(degree="B.Tech Computer Science")],
        projects=["Built AI Parser"]
    )

    match = MatchAnalysisSchema(
        matching_skills=["Python", "FastAPI", "SQL", "Machine Learning"],
        missing_skills=[],
        experience_analysis="Candidate has 3.5 years experience exceeding required 2.0 years.",
        education_analysis="B.Tech degree matches requirement.",
        responsibilities_match="Strong alignment with backend development responsibilities."
    )

    eval_data = EvaluationSchema(
        overall_summary="Excellent fit for AI Engineer role.",
        strengths=["3.5 years Python experience", "Full skills overlap"],
        concerns=[],
        recruiter_recommendation="RECOMMENDED FOR INTERVIEW"
    )

    scorer = ATSScorer()
    res = scorer.calculate_score(job, candidate, match, eval_data)

    assert res.score.overall >= 85.0
    assert res.decision == DecisionEnum.STRONG_SHORTLIST
    assert not res.mandatory_failed


def test_scorer_mandatory_experience_override():
    job = JobDescriptionData(
        job_title="Senior AI Engineer",
        required_skills=["Python", "FastAPI"],
        required_experience_years=5.0
    )

    candidate = CandidateData(
        candidate_name="Junior Dev",
        skills=["Python", "FastAPI"],
        total_experience_years=1.5
    )

    match = MatchAnalysisSchema(
        matching_skills=["Python", "FastAPI"],
        missing_skills=[]
    )

    eval_data = EvaluationSchema(
        overall_summary="Junior candidate.",
        strengths=["Good Python skills"],
        concerns=["Lacks required 5 years experience"]
    )

    scorer = ATSScorer()
    res = scorer.calculate_score(job, candidate, match, eval_data)

    assert res.mandatory_failed is True
    assert "Mandatory experience requirement not satisfied" in res.mandatory_failure_reason
    assert res.decision in [DecisionEnum.REVIEW, DecisionEnum.REJECT]
