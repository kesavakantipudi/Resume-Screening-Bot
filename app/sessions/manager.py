import json
import uuid
import logging
import asyncio
from typing import Optional, List
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.session import RecruitmentSession, SessionState
from app.models.job import JobDescriptionDB, JobDescriptionData
from app.models.candidate import CandidateDB, CandidateData
from app.models.analysis import CandidateAnalysisDB, CandidateAnalysisResult
from app.platforms.base import UnifiedMessage, PlatformAdapter
from app.platforms.factory import PlatformAdapterFactory
from app.documents.downloader import save_temp_file, cleanup_file
from app.documents.extractor import extract_text_from_file
from app.documents.classifier import DocumentClassifier
from app.recruitment.jd_analyzer import JobDescriptionAnalyzer
from app.recruitment.resume_analyzer import ResumeAnalyzer
from app.recruitment.matcher import CandidateMatcher
from app.recruitment.scorer import ATSScorer
from app.recruitment.ranker import CandidateRanker
from app.recruitment.report import RecruitmentReportGenerator
from app.config.settings import settings

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self):
        self.jd_analyzer = JobDescriptionAnalyzer()
        self.resume_analyzer = ResumeAnalyzer()
        self.matcher = CandidateMatcher()
        self.scorer = ATSScorer()
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_ANALYSES)

    def get_or_create_session(self, db: Session, platform: str, user_id: str, conversation_id: str) -> RecruitmentSession:
        session_obj = (
            db.query(RecruitmentSession)
            .filter(
                RecruitmentSession.platform == platform,
                RecruitmentSession.conversation_id == conversation_id
            )
            .first()
        )
        if not session_obj:
            session_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
            session_obj = RecruitmentSession(
                id=session_id,
                platform=platform,
                user_id=user_id,
                conversation_id=conversation_id,
                status=SessionState.WAITING_FOR_INPUT
            )
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
        return session_obj

    async def handle_message(self, message: UnifiedMessage) -> str:
        """
        Main entry point for handling an incoming UnifiedMessage from any messaging platform.
        Returns the text response to send back to the user.
        """
        db: Session = SessionLocal()
        try:
            adapter: PlatformAdapter = PlatformAdapterFactory.get_adapter(message.platform)
            session_obj = self.get_or_create_session(db, message.platform, message.user_id, message.conversation_id)

            clean_text = (message.text or "").strip()
            command = clean_text.upper()

            # Handle Commands
            if command in ["/START", "/HELP"]:
                return (
                    "👋 Welcome to HireLens AI Recruitment Assistant!\n\n"
                    "Workflow Instructions:\n"
                    "• Upload your Job Description (PDF, DOCX, TXT, or text message).\n"
                    "• Upload candidate resumes (PDF, DOCX, TXT) at any time.\n"
                    "• Send 'ANALYZE' to generate ATS compatibility scores and candidate rankings.\n\n"
                    "Available Commands:\n"
                    "/new — Start a fresh recruitment session\n"
                    "/status — Check current session status\n"
                    "/reset — Reset active session\n"
                    "/jd — Explicitly upload/specify Job Description\n"
                    "/resume — Explicitly upload candidate resume\n"
                    "DETAIL <number or Name> — View deep dive report for candidate"
                )

            elif command in ["/NEW", "NEW JOB"]:
                db.delete(session_obj)
                db.commit()
                session_obj = self.get_or_create_session(db, message.platform, message.user_id, message.conversation_id)
                return "📋 New recruitment session created. You can upload the Job Description or candidate resumes at any time."

            elif command in ["/RESET"]:
                db.delete(session_obj)
                db.commit()
                return "🔄 Session reset successfully. Use /new to start a new job screening session."

            elif command in ["/STATUS"]:
                candidate_count = session_obj.resume_count
                jd_title = session_obj.job_description.title if session_obj.job_description else "Not provided yet"
                return (
                    f"📊 Session Status: {session_obj.status.value}\n"
                    f"Session ID: {session_obj.id}\n"
                    f"Job Description: {jd_title}\n"
                    f"Resumes Uploaded: {candidate_count}\n"
                )

            elif command in ["ANALYZE", "/ANALYZE"]:
                return await self._run_analysis_pipeline(db, session_obj, adapter)

            elif command.startswith("DETAIL") or command.startswith("/RESULTS"):
                return self._get_detail_report(db, session_obj, clean_text)

            # Handle File Attachments
            if message.attachments:
                return await self._handle_attachments(db, session_obj, message, adapter)

            # Handle Text-only messages (e.g. user pasted JD or sent text)
            if clean_text:
                return await self._handle_text_document(db, session_obj, clean_text)

            return "⚠️ Unrecognized command or message. Upload a Job Description file or candidate resumes, or send /help for instructions."

        except Exception as e:
            logger.error(f"Error handling message for session: {e}", exc_info=True)
            return f"❌ An error occurred while processing your request: {str(e)}"
        finally:
            db.close()

    async def _handle_attachments(
        self, db: Session, session_obj: RecruitmentSession, message: UnifiedMessage, adapter: PlatformAdapter
    ) -> str:
        initial_jd_state = session_obj.jd_received
        initial_resume_count = session_obj.resume_count

        jd_added = False
        resumes_added = 0
        resumes_updated = 0
        uncertain_files = []
        errors = []

        clean_text = (message.text or "").strip()

        for attachment in message.attachments:
            try:
                file_bytes = attachment.data_bytes
                if not file_bytes:
                    file_bytes = await adapter.download_file(attachment.file_id)

                temp_path = save_temp_file(file_bytes, attachment.filename)
                try:
                    extracted_text = extract_text_from_file(temp_path, attachment.filename)
                finally:
                    cleanup_file(temp_path)

                # Classify document
                doc_type = DocumentClassifier.classify(extracted_text, filename=attachment.filename, caption=clean_text)

                if doc_type == "job_description":
                    await self._save_job_description_db(db, session_obj, attachment.filename, extracted_text)
                    jd_added = True
                elif doc_type == "resume":
                    is_new = await self._save_candidate_resume_db(db, session_obj, attachment.filename, extracted_text)
                    if is_new:
                        resumes_added += 1
                    else:
                        resumes_updated += 1
                else:
                    # Uncertain classification
                    uncertain_files.append(attachment.filename)

            except Exception as e:
                logger.error(f"Failed attachment processing for {attachment.filename}: {e}")
                errors.append(f"❌ Error parsing '{attachment.filename}': {str(e)}")

        # Update Session State
        self._update_session_status(session_obj)
        db.commit()

        # Build Response Message
        responses = []
        if errors:
            responses.extend(errors)

        if uncertain_files:
            for fname in uncertain_files:
                responses.append(
                    f"⚠️ I'm uncertain whether '{fname}' is a Job Description or a candidate resume.\n"
                    "Should I treat this document as the Job Description or a candidate resume? Reply with /JD or /RESUME."
                )

        total_processed_resumes = resumes_added + resumes_updated

        if jd_added and total_processed_resumes > 0:
            responses.append(
                f"Received the Job Description and {session_obj.resume_count} resumes.\n"
                "Send ANALYZE when you're ready to start screening."
            )
        elif jd_added:
            if session_obj.resume_count > 0:
                responses.append(
                    f"Job Description received successfully.\n"
                    f"You have {session_obj.resume_count} resumes ready for analysis.\n"
                    "Send ANALYZE to start the screening."
                )
            else:
                responses.append("Job Description received successfully.\nNow upload the candidate resumes.")
        elif resumes_added > 0:
            if session_obj.jd_received:
                responses.append(
                    f"{resumes_added} resumes received ({session_obj.resume_count} candidate(s) in total).\n"
                    "Send ANALYZE when ready."
                )
            else:
                responses.append(
                    f"I received {resumes_added} resumes, but I don't have a Job Description yet ({session_obj.resume_count} candidate(s) in total).\n"
                    "Please upload or send the Job Description before I can analyze the candidates."
                )
        elif resumes_updated > 0:
            if session_obj.jd_received:
                responses.append(
                    f"Updated {resumes_updated} existing candidate resume(s) ({session_obj.resume_count} candidate(s) in total).\n"
                    "Send ANALYZE when ready."
                )
            else:
                responses.append(
                    f"Updated {resumes_updated} existing candidate resume(s) ({session_obj.resume_count} candidate(s) in total), but I don't have a Job Description yet.\n"
                    "Please upload or send the Job Description before I can analyze the candidates."
                )

        return "\n\n".join(responses) if responses else "File processed."

    async def _handle_text_document(
        self, db: Session, session_obj: RecruitmentSession, text: str
    ) -> str:
        doc_type = DocumentClassifier.classify(text, caption=text)

        if doc_type == "job_description":
            await self._save_job_description_db(db, session_obj, "Job Description Text", text)
            self._update_session_status(session_obj)
            db.commit()

            if session_obj.resume_count > 0:
                return (
                    f"Job Description received successfully.\n"
                    f"You have {session_obj.resume_count} candidate(s) ready for analysis.\n"
                    "Send ANALYZE to start the screening."
                )
            else:
                return "Job Description received successfully.\nPlease upload the candidate resumes."

        elif doc_type == "resume":
            is_new = await self._save_candidate_resume_db(db, session_obj, "Pasted Resume Text", text)
            self._update_session_status(session_obj)
            db.commit()

            status_desc = "Received 1 new resume" if is_new else "Updated existing candidate resume"

            if session_obj.jd_received:
                return f"{status_desc} ({session_obj.resume_count} candidate(s) in total).\nSend ANALYZE when ready."
            else:
                return (
                    f"{status_desc} ({session_obj.resume_count} candidate(s) in total), but I don't have a Job Description yet.\n"
                    "Please upload or send the Job Description before I can analyze the candidates."
                )
        else:
            return (
                "⚠️ I couldn't determine if this text is a Job Description or a candidate resume.\n"
                "Please prefix with /JD or /RESUME or upload a document file."
            )

    async def _save_job_description_db(
        self, db: Session, session_obj: RecruitmentSession, filename: str, raw_text: str
    ):
        if session_obj.job_description:
            db.delete(session_obj.job_description)
            db.commit()

        job_db = JobDescriptionDB(
            id=f"JOB-{uuid.uuid4().hex[:8]}",
            session_id=session_obj.id,
            title=filename,
            raw_text=raw_text,
            structured_data_json="{}"
        )
        db.add(job_db)

    async def _save_candidate_resume_db(
        self, db: Session, session_obj: RecruitmentSession, filename: str, raw_text: str
    ) -> bool:
        """
        Save candidate resume to DB. If a candidate with the same filename or matching text
        already exists in this session, update the existing candidate instead of creating a duplicate.
        Returns True if a new candidate was created, False if an existing candidate was updated.
        """
        clean_raw = raw_text.strip()
        existing = None

        if session_obj.candidates:
            for cand in session_obj.candidates:
                # Match by filename (excluding generic pasted text)
                if filename and filename != "Pasted Resume Text" and cand.filename and cand.filename.lower() == filename.lower():
                    existing = cand
                    break
                # Match by exact raw text content
                if cand.raw_text and cand.raw_text.strip() == clean_raw:
                    existing = cand
                    break

        if existing:
            logger.info(f"Duplicate document detected ({filename}). Updating existing candidate {existing.id}.")
            existing.filename = filename
            existing.raw_text = raw_text
            existing.structured_data_json = "{}"
            if existing.analysis:
                db.delete(existing.analysis)
            db.flush()
            return False
        else:
            cand_db = CandidateDB(
                id=f"CAND-{uuid.uuid4().hex[:8]}",
                session_id=session_obj.id,
                filename=filename,
                name=filename,
                raw_text=raw_text,
                structured_data_json="{}"
            )
            db.add(cand_db)
            db.flush()
            return True

    def _update_session_status(self, session_obj: RecruitmentSession):
        has_jd = session_obj.jd_received
        has_resumes = session_obj.resume_count > 0

        if has_jd and has_resumes:
            session_obj.status = SessionState.READY_FOR_ANALYSIS
        elif has_jd:
            session_obj.status = SessionState.COLLECTING_RESUMES
        elif has_resumes:
            session_obj.status = SessionState.WAITING_FOR_JD
        else:
            session_obj.status = SessionState.WAITING_FOR_INPUT

    async def _run_analysis_pipeline(
        self, db: Session, session_obj: RecruitmentSession, adapter: PlatformAdapter
    ) -> str:
        has_jd = session_obj.jd_received
        has_resumes = session_obj.resume_count > 0

        # Step 1 & 2: Validate presence of JD and Resumes before starting Gemini analysis
        if not has_jd and not has_resumes:
            return "Please provide a Job Description and at least one candidate resume before starting the analysis."
        elif not has_jd:
            return "I don't have a Job Description for this screening session yet. Please upload or send the Job Description first."
        elif not has_resumes:
            return "Please upload at least one candidate resume before starting the analysis."

        session_obj.status = SessionState.ANALYZING
        db.commit()

        candidates = session_obj.candidates

        # Send status update message to user
        await adapter.send_message(
            session_obj.user_id,
            session_obj.conversation_id,
            f"⚙️ Analyzing {len(candidates)} candidates against Job Description... Please wait."
        )

        try:
            # 1. Parse JD with Gemini if not cached
            jd_db = session_obj.job_description
            if jd_db.structured_data_json == "{}" or not jd_db.structured_data_json:
                jd_struct = await self.jd_analyzer.analyze(jd_db.raw_text)
                jd_db.title = jd_struct.job_title or jd_db.title
                jd_db.structured_data_json = json.dumps(jd_struct.model_dump())
                db.commit()
            else:
                jd_struct = jd_db.structured_data

            # 2. Concurrently analyze candidates with Gemini and ATS Scorer
            async def _analyze_single_candidate(cand_db: CandidateDB) -> CandidateAnalysisResult:
                async with self.semaphore:
                    # Parse candidate struct
                    if cand_db.structured_data_json == "{}" or not cand_db.structured_data_json:
                        cand_struct = await self.resume_analyzer.analyze(cand_db.raw_text)
                        cand_db.name = cand_struct.candidate_name or cand_db.filename
                        cand_db.structured_data_json = json.dumps(cand_struct.model_dump())
                    else:
                        cand_struct = cand_db.structured_data

                    # Match & evaluate
                    match_data, eval_data = await self.matcher.match_and_evaluate(jd_struct, cand_struct)

                    # Calculate ATS score & mandatory overrides
                    analysis_result = self.scorer.calculate_score(
                        jd_struct, cand_struct, match_data, eval_data, model_used=self.matcher.ai_provider.last_used_model
                    )
                    analysis_result.candidate_id = cand_db.id

                    # Save to DB (update in-place if analysis already exists to avoid unique constraint flush conflicts)
                    if cand_db.analysis:
                        cand_db.analysis.score = analysis_result.score.overall
                        cand_db.analysis.decision = analysis_result.decision
                        cand_db.analysis.mandatory_failed = analysis_result.mandatory_failed
                        cand_db.analysis.mandatory_failure_reason = analysis_result.mandatory_failure_reason
                        cand_db.analysis.analysis_json = json.dumps(analysis_result.model_dump())
                        analysis_db = cand_db.analysis
                    else:
                        analysis_db = CandidateAnalysisDB(
                            id=f"ANALYSIS-{uuid.uuid4().hex[:8]}",
                            candidate_id=cand_db.id,
                            score=analysis_result.score.overall,
                            decision=analysis_result.decision,
                            mandatory_failed=analysis_result.mandatory_failed,
                            mandatory_failure_reason=analysis_result.mandatory_failure_reason,
                            analysis_json=json.dumps(analysis_result.model_dump())
                        )
                        db.add(analysis_db)

                    db.flush()
                    return analysis_result

            tasks = [_analyze_single_candidate(c) for c in candidates]
            results: List[CandidateAnalysisResult] = await asyncio.gather(*tasks)

            # 3. Rank candidates
            ranked_results = CandidateRanker.rank_candidates(results)

            session_obj.status = SessionState.COMPLETED
            db.commit()

            # 4. Generate Ranking Report
            report_text = RecruitmentReportGenerator.generate_ranking_report(jd_struct.job_title, ranked_results)
            return report_text

        except Exception as e:
            db.rollback()
            self._update_session_status(session_obj)
            db.commit()
            logger.error(f"Analysis pipeline error: {e}", exc_info=True)
            return f"⚠️ Candidate analysis temporarily failed: {str(e)}\nPlease try again with ANALYZE."

    def _get_detail_report(self, db: Session, session_obj: RecruitmentSession, command_text: str) -> str:
        parts = command_text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""

        if not session_obj.candidates:
            return "⚠️ No candidates available in this session."

        analyses = [c.analysis.result for c in session_obj.candidates if c.analysis]
        if not analyses:
            return "⚠️ Candidates have not been analyzed yet. Run ANALYZE first."

        ranked_results = CandidateRanker.rank_candidates(analyses)

        target_analysis = None
        if query.isdigit():
            idx = int(query) - 1
            if 0 <= idx < len(ranked_results):
                target_analysis = ranked_results[idx]
        elif query:
            for item in ranked_results:
                if query.lower() in item.candidate_name.lower():
                    target_analysis = item
                    break

        if not target_analysis and ranked_results:
            target_analysis = ranked_results[0]

        if not target_analysis:
            return "⚠️ Could not find candidate matching your query."

        return RecruitmentReportGenerator.generate_candidate_detail_report(target_analysis)
