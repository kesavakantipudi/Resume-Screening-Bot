from typing import List
from app.models.analysis import CandidateAnalysisResult, DecisionEnum


class RecruitmentReportGenerator:
    @staticmethod
    def generate_ranking_report(job_title: str, ranked_results: List[CandidateAnalysisResult]) -> str:
        """
        Generate the executive batch ranking report for messaging platforms.
        """
        total = len(ranked_results)
        medals = ["🥇", "🥈", "🥉"]

        shortlist_count = sum(1 for r in ranked_results if r.decision in [DecisionEnum.STRONG_SHORTLIST, DecisionEnum.SHORTLIST])
        review_count = sum(1 for r in ranked_results if r.decision == DecisionEnum.REVIEW)
        reject_count = sum(1 for r in ranked_results if r.decision == DecisionEnum.REJECT)

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            "📋 HIRING SCREENING REPORT",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"Position: {job_title}",
            f"Candidates Analyzed: {total}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━",
            ""
        ]

        for idx, item in enumerate(ranked_results, 1):
            prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
            fail_flag = " ⚠️ (Mandatory Gap)" if item.mandatory_failed else ""
            lines.append(f"{prefix} {item.candidate_name}")
            lines.append(f"   ATS Score: {item.score.overall:.0f}/100")
            lines.append(f"   Decision: {item.decision.value}{fail_flag}")
            lines.append("")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"Recommended Interviews: {shortlist_count}",
            f"Needs Review: {review_count}",
            f"Rejected: {reject_count}",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "💡 Type 'DETAIL <number>' or 'DETAIL <Name>' for a full candidate report."
        ])

        return "\n".join(lines)

    @staticmethod
    def generate_candidate_detail_report(result: CandidateAnalysisResult) -> str:
        """
        Generate detailed evidence-based recruiter report for an individual candidate.
        """
        matched_str = "\n".join([f"  ✓ {s}" for s in result.matching_skills]) if result.matching_skills else "  None explicitly identified"
        missing_str = "\n".join([f"  ✗ {s}" for s in result.missing_skills]) if result.missing_skills else "  None"
        strengths_str = "\n".join([f"  • {s}" for s in result.strengths]) if result.strengths else "  None listed"
        concerns_str = "\n".join([f"  • {s}" for s in result.concerns]) if result.concerns else "  No major concerns"
        
        mandatory_warning = ""
        if result.mandatory_failed:
            mandatory_warning = f"\n⚠️ MANDATORY REQUIREMENT OVERRIDE:\n{result.mandatory_failure_reason}\n"

        lines = [
            f"👤 CANDIDATE SCREENING REPORT: {result.candidate_name}",
            "═" * 38,
            f"Overall Decision: {result.decision.value}",
            f"ATS Score: {result.score.overall:.0f}/100",
            mandatory_warning,
            "📊 Score Breakdown:",
            f"  • Required Skills:    {result.score.required_skills:.1f} / 35.0",
            f"  • Experience Match:   {result.score.experience:.1f} / 20.0",
            f"  • Responsibilities:   {result.score.responsibilities:.1f} / 15.0",
            f"  • Education:          {result.score.education:.1f} / 10.0",
            f"  • Preferred Skills:   {result.score.preferred_skills:.1f} / 10.0",
            f"  • Projects:           {result.score.projects:.1f} / 5.0",
            f"  • Certifications:     {result.score.certifications:.1f} / 5.0",
            "",
            "📝 Executive Match Summary:",
            f"{result.overall_summary}",
            "",
            "✅ Matching Skills:",
            matched_str,
            "",
            "❌ Missing Skills:",
            missing_str,
            "",
            "💼 Experience Analysis:",
            f"  {result.experience_analysis}",
            "",
            "🎓 Education Analysis:",
            f"  {result.education_analysis}",
            "",
            "💪 Key Strengths:",
            strengths_str,
            "",
            "⚠️ Concerns / Gaps:",
            concerns_str,
            "",
            "🎯 Recruiter Recommendation:",
            f"  {result.recruiter_recommendation}",
            "═" * 38
        ]

        return "\n".join(lines)
