import logging
from app.models.job import JobDescriptionData
from app.models.candidate import CandidateData
from app.models.analysis import ATSScoreBreakdown, DecisionEnum, CandidateAnalysisResult, EvidenceItem
from app.recruitment.matcher import MatchAnalysisSchema, EvaluationSchema
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ATSScorer:
    def calculate_score(
        self,
        job_data: JobDescriptionData,
        candidate_data: CandidateData,
        match_data: MatchAnalysisSchema,
        eval_data: EvaluationSchema,
        model_used: str = ""
    ) -> CandidateAnalysisResult:
        """
        Calculate deterministic ATS score based on structured criteria and enforce mandatory requirement overrides.
        """
        # 1. Required Skills Score (Max 35 points)
        required_skills_pts = 0.0
        if job_data.required_skills:
            total_req = len(job_data.required_skills)
            matched_req = len(match_data.matching_skills)
            # Clip matched_req to total_req
            matched_ratio = min(1.0, matched_req / total_req) if total_req > 0 else 1.0
            required_skills_pts = round(matched_ratio * 35.0, 2)
        else:
            required_skills_pts = 35.0  # If no explicit required skills specified

        # 2. Relevant Experience Score (Max 20 points)
        experience_pts = 0.0
        req_years = job_data.required_experience_years
        cand_years = candidate_data.total_experience_years

        if req_years <= 0.0:
            experience_pts = 20.0
        else:
            if cand_years >= req_years:
                experience_pts = 20.0
            else:
                ratio = cand_years / req_years
                experience_pts = round(ratio * 20.0, 2)

        # 3. Responsibilities Match (Max 15 points)
        responsibilities_pts = 12.0  # Default baseline
        if match_data.responsibilities_match:
            # Check length/quality of match string
            text_len = len(match_data.responsibilities_match)
            if "strong" in match_data.responsibilities_match.lower() or text_len > 100:
                responsibilities_pts = 14.5
            elif "partial" in match_data.responsibilities_match.lower():
                responsibilities_pts = 10.0
            elif "minimal" in match_data.responsibilities_match.lower():
                responsibilities_pts = 6.0
        elif candidate_data.experience:
            responsibilities_pts = 13.0

        # 4. Education Match (Max 10 points)
        education_pts = 8.0
        if job_data.education_requirements:
            req_edu_str = " ".join(job_data.education_requirements).lower()
            cand_edu_str = " ".join([e.degree for e in candidate_data.education]).lower()
            if any(term in cand_edu_str for term in ["b.tech", "m.tech", "b.s", "m.s", "phd", "bachelor", "master"]):
                education_pts = 10.0
            elif cand_edu_str:
                education_pts = 8.5
        else:
            education_pts = 10.0

        # 5. Preferred Skills Score (Max 10 points)
        preferred_skills_pts = 5.0
        if job_data.preferred_skills:
            cand_skills_lower = [s.lower() for s in candidate_data.skills]
            matched_pref = sum(
                1 for p in job_data.preferred_skills
                if any(p.lower() in s or s in p.lower() for s in cand_skills_lower)
            )
            ratio = matched_pref / len(job_data.preferred_skills)
            preferred_skills_pts = round(ratio * 10.0, 2)

        # 6. Projects / Achievements Score (Max 5 points)
        projects_pts = 0.0
        project_count = len(candidate_data.projects) + len(candidate_data.achievements)
        if project_count >= 3:
            projects_pts = 5.0
        elif project_count == 2:
            projects_pts = 4.0
        elif project_count == 1:
            projects_pts = 3.0
        else:
            projects_pts = 2.0

        # 7. Certifications Score (Max 5 points)
        certifications_pts = 2.5
        if candidate_data.certifications:
            certifications_pts = 5.0

        # Overall Score Sum
        overall_score = round(
            required_skills_pts
            + experience_pts
            + responsibilities_pts
            + education_pts
            + preferred_skills_pts
            + projects_pts
            + certifications_pts,
            2
        )
        overall_score = min(100.0, max(0.0, overall_score))

        score_breakdown = ATSScoreBreakdown(
            required_skills=required_skills_pts,
            experience=experience_pts,
            responsibilities=responsibilities_pts,
            education=education_pts,
            preferred_skills=preferred_skills_pts,
            projects=projects_pts,
            certifications=certifications_pts,
            overall=overall_score
        )

        # Initial Unrestricted Recommendation Decision
        if overall_score >= settings.SCORE_STRONG_SHORTLIST:
            decision = DecisionEnum.STRONG_SHORTLIST
        elif overall_score >= settings.SCORE_SHORTLIST:
            decision = DecisionEnum.SHORTLIST
        elif overall_score >= settings.SCORE_REVIEW:
            decision = DecisionEnum.REVIEW
        else:
            decision = DecisionEnum.REJECT

        # Check Mandatory Requirement Overrides
        mandatory_failed = False
        mandatory_reasons = []

        # Override Rule A: Experience Gap
        if req_years > 0 and cand_years < req_years:
            mandatory_failed = True
            mandatory_reasons.append(
                f"Mandatory experience requirement not satisfied (Required: {req_years} yrs, Candidate: {cand_years} yrs)."
            )

        # Override Rule B: Critical Missing Required Skills (> 50% missing)
        if job_data.required_skills:
            missing_count = len(match_data.missing_skills)
            total_req = len(job_data.required_skills)
            if missing_count / total_req > 0.5:
                mandatory_failed = True
                missing_str = ", ".join(match_data.missing_skills)
                mandatory_reasons.append(f"Missing >50% of mandatory skills ({missing_str}).")

        mandatory_failure_reason = None
        if mandatory_failed:
            mandatory_failure_reason = " ".join(mandatory_reasons)
            # Downgrade decision
            if decision in [DecisionEnum.STRONG_SHORTLIST, DecisionEnum.SHORTLIST]:
                decision = DecisionEnum.REVIEW if overall_score >= settings.SCORE_REVIEW else DecisionEnum.REJECT
                logger.info(
                    f"Downgraded candidate {candidate_data.candidate_name} decision to {decision} due to mandatory failure."
                )

        return CandidateAnalysisResult(
            candidate_name=candidate_data.candidate_name,
            score=score_breakdown,
            decision=decision,
            mandatory_failed=mandatory_failed,
            mandatory_failure_reason=mandatory_failure_reason,
            overall_summary=eval_data.overall_summary or f"Candidate scored {overall_score}/100.",
            matching_skills=match_data.matching_skills,
            missing_skills=match_data.missing_skills,
            experience_analysis=match_data.experience_analysis or f"Candidate has {cand_years} years total experience.",
            education_analysis=match_data.education_analysis or "Education match verified.",
            responsibilities_match=match_data.responsibilities_match,
            relevant_projects=match_data.relevant_projects or candidate_data.projects,
            certifications_analysis=match_data.certifications_analysis or ", ".join(candidate_data.certifications),
            strengths=eval_data.strengths or [f"Scored {required_skills_pts}/35 in required skills."],
            concerns=eval_data.concerns or ([] if not mandatory_failed else [mandatory_failure_reason]),
            potential_red_flags=eval_data.potential_red_flags,
            recruiter_recommendation=eval_data.recruiter_recommendation or f"Decision: {decision.value}",
            evidence_notes=match_data.evidence_notes,
            model_used=model_used or settings.GEMINI_MODEL
        )
