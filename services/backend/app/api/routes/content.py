from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.routes.health import authorize
from app.core.config import settings
from app.db import session as db_session
from app.db.session import get_session
from app.models import (Claim, ClaimSource, FactCheckResult, NarrationSegment, Project, ProviderConfiguration, ResearchSession, ResearchSource,
                        ScriptDocument, ScriptSection, ScriptVersion, Storyboard, StoryboardScene)
from app.schemas.content import (ClaimOut, ClaimReview, NarrationConfig, NarrationSegmentUpdate, ResearchStart, ResearchStatus,
                                 ProviderConfigurationUpdate, SceneUpdate, ScriptGenerate, SectionApproval, SectionUpdate, SourceOut)
from app.services.content import ResearchOrchestrator, SECTION_ORDER, clean_script_sections, persist_research, segment_narration
from app.services.providers import ProviderUnavailable, configured_ai_provider, configured_search_provider

router = APIRouter(dependencies=[Depends(authorize)])
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="geochronicle-content")
_starting: set[int] = set()
_starting_lock = Lock()


def _missing(kind: str) -> HTTPException:
    return HTTPException(404, {"code": f"{kind}_not_found", "message": f"{kind.replace('_', ' ').title()} was not found"})


def _date(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _session_out(row: ResearchSession) -> dict[str, Any]:
    return {"id": row.id, "project_id": row.project_id, "topic": row.topic, "configuration": row.configuration,
            "status": row.status, "progress": row.progress, "error": row.error,
            "overview": row.results.get("overview"), "perspectives": row.results.get("perspectives", []),
            "created_at": _date(row.created_at), "completed_at": _date(row.completed_at)}


def _run_research(session_id: int, project_id: int) -> None:
    factory = db_session.SessionLocal
    if factory is None:
        with _starting_lock:
            _starting.discard(project_id)
        return
    db: Session = factory()
    try:
        row = db.get(ResearchSession, session_id)
        if row is None:
            return
        row.status, row.progress = "running", "Searching configured sources"
        db.commit()
        output = ResearchOrchestrator(configured_search_provider(), configured_ai_provider()).research(row.topic, row.configuration)
        persist_research(row, output)
        row.results = {"overview": output["overview"], "perspectives": output["perspectives"]}
        row.status, row.progress, row.error = "completed", "Research ready for review", None
        row.completed_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:
        db.rollback()
        row = db.get(ResearchSession, session_id)
        if row:
            row.status, row.progress = "failed", None
            row.error = str(exc)[:500] if isinstance(exc, ProviderUnavailable) else "Research could not be completed. Check provider settings and retry."
            row.completed_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()
        with _starting_lock:
            _starting.discard(project_id)


def _claim_out(claim: Claim) -> dict[str, Any]:
    return {"id": claim.id, "session_id": claim.session_id, "text": claim.text, "category": claim.category,
            "verification_status": claim.verification_status, "confidence": claim.confidence, "reviewer_notes": claim.reviewer_notes,
            "sources": [{"id": link.source.id, "title": link.source.title, "url": link.source.url,
                         "publisher": link.source.publisher, "relationship_type": link.relationship_type, "evidence": link.evidence}
                        for link in claim.source_links]}


def _scene_out(scene: StoryboardScene) -> dict[str, Any]:
    return {"id": scene.id, "scene_number": scene.scene_number, "title": scene.title, "script_section_key": scene.script_section_key, "narration_text": scene.narration_text,
            "description": scene.description, "duration_seconds": scene.duration_seconds, "visual_direction": scene.visual_direction,
            "historical_events": scene.historical_events, "geographic_references": scene.geographic_references,
            "claim_ids": scene.claim_ids, "source_ids": scene.source_ids, "transition_suggestion": scene.transition_suggestion}


def _script_out(script: ScriptDocument) -> dict[str, Any]:
    return {"id": script.id, "project_id": script.project_id, "research_session_id": script.research_session_id,
            "title": script.title, "updated_at": _date(script.updated_at),
            "sections": [{"id": x.id, "section_key": x.section_key, "title": x.title, "content": x.content, "approved": x.approved, "position": x.position} for x in sorted(script.sections, key=lambda item: item.position)]}


def _load_script(db: Session, script_id: int) -> ScriptDocument:
    row = db.scalar(select(ScriptDocument).where(ScriptDocument.id == script_id).options(selectinload(ScriptDocument.sections)))
    if row is None:
        raise _missing("script")
    return row


def _snapshot(db: Session, script: ScriptDocument, note: str) -> None:
    db.flush()
    current = db.scalar(select(func.max(ScriptVersion.version_number)).where(ScriptVersion.script_id == script.id)) or 0
    sections = [{"section_key": x.section_key, "title": x.title, "content": x.content, "approved": x.approved, "position": x.position} for x in sorted(script.sections, key=lambda item: item.position)]
    db.add(ScriptVersion(script_id=script.id, version_number=current + 1, sections_snapshot=sections, change_note=note))


def _clear_section_narration(db: Session, script_id: int, section_key: str) -> None:
    scene_ids = select(StoryboardScene.id).join(Storyboard).where(Storyboard.script_id == script_id, StoryboardScene.script_section_key == section_key)
    db.query(NarrationSegment).filter(NarrationSegment.scene_id.in_(scene_ids)).delete(synchronize_session=False)


def _provider_rows(db: Session) -> dict[str, ProviderConfiguration]:
    return {row.provider_name: row for row in db.scalars(select(ProviderConfiguration).where(ProviderConfiguration.provider_name.in_(("search", "ai"))).order_by(ProviderConfiguration.id)).all()}


@router.get("/providers")
def provider_status(db: Session = Depends(get_session)) -> dict[str, Any]:
    # Never disclose credential material or local credential-store diagnostics.
    import keyring
    def available(service: str) -> bool:
        try:
            return bool(keyring.get_password("GeoChronicle", service))
        except Exception:
            return False
    rows = _provider_rows(db)
    search = rows.get("search")
    ai = rows.get("ai")
    search_endpoint = search.configuration.get("endpoint", settings.search_endpoint) if search else settings.search_endpoint
    ai_endpoint = ai.configuration.get("endpoint", settings.ai_endpoint) if ai else settings.ai_endpoint
    return {"search_provider": settings.search_provider, "search_endpoint": search_endpoint, "search_available": settings.search_provider == "tavily" and available("tavily"),
            "ai_provider": settings.ai_provider, "ai_endpoint": ai_endpoint, "ai_model": settings.ai_model,
            "ai_available": settings.ai_provider == "openai_compatible" and available("openai"),
            "credentials_store": "Windows Credential Manager"}


@router.patch("/providers/configuration")
def update_provider_configuration(payload: ProviderConfigurationUpdate, db: Session = Depends(get_session)):
    values = payload.model_dump(exclude_unset=True)
    rows = _provider_rows(db)
    if "search_provider" in values or "search_endpoint" in values:
        row = rows.get("search") or ProviderConfiguration(provider_name="search", enabled=False, configuration={})
        if "search_provider" in values:
            settings.search_provider = values["search_provider"]
            row.enabled = values["search_provider"] != "none"
            row.configuration = {**(row.configuration or {}), "provider": values["search_provider"]}
        if "search_endpoint" in values:
            settings.search_endpoint = values["search_endpoint"]
            row.configuration = {**(row.configuration or {}), "endpoint": values["search_endpoint"]}
        if row.id is None:
            db.add(row)
    if "ai_provider" in values or "ai_endpoint" in values or "ai_model" in values:
        row = rows.get("ai") or ProviderConfiguration(provider_name="ai", enabled=False, configuration={})
        if "ai_provider" in values:
            settings.ai_provider = values["ai_provider"]
            row.enabled = values["ai_provider"] != "none"
            row.configuration = {**(row.configuration or {}), "provider": values["ai_provider"]}
        if "ai_endpoint" in values:
            settings.ai_endpoint = values["ai_endpoint"]
            row.configuration = {**(row.configuration or {}), "endpoint": values["ai_endpoint"]}
        if "ai_model" in values:
            settings.ai_model = values["ai_model"]
            row.model_name = values["ai_model"]
        if row.id is None:
            db.add(row)
    db.commit()
    return provider_status(db)


@router.post("/projects/{project_id}/research-sessions", response_model=ResearchStatus, status_code=202)
def start_research(project_id: int, payload: ResearchStart, background: BackgroundTasks, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if project is None:
        raise _missing("project")
    topic = (payload.topic or project.topic or "").strip()
    if not topic:
        raise HTTPException(422, {"code": "topic_required", "message": "Add a topic to the project before starting research."})
    with _starting_lock:
        if project_id in _starting:
            raise HTTPException(409, {"code": "research_in_progress", "message": "Research is already running for this project."})
        _starting.add(project_id)
    row = ResearchSession(project_id=project_id, topic=topic, configuration=payload.model_dump(), status="pending", progress="Queued")
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        with _starting_lock:
            _starting.discard(project_id)
        raise
    # BackgroundTasks runs after the response; the executor bounds concurrent provider work.
    def submit() -> None:
        _executor.submit(_run_research, row.id, project_id)
    background.add_task(submit)
    return _session_out(row)


@router.get("/projects/{project_id}/research-sessions", response_model=list[ResearchStatus])
def list_research(project_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50), db: Session = Depends(get_session)):
    if db.get(Project, project_id) is None:
        raise _missing("project")
    rows = db.scalars(select(ResearchSession).where(ResearchSession.project_id == project_id).order_by(ResearchSession.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return [_session_out(x) for x in rows]


@router.get("/research-sessions/{session_id}", response_model=ResearchStatus)
def get_research(session_id: int, db: Session = Depends(get_session)):
    row = db.get(ResearchSession, session_id)
    if row is None:
        raise _missing("research_session")
    return _session_out(row)


@router.get("/research-sessions/{session_id}/sources", response_model=list[SourceOut])
def list_sources(session_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), db: Session = Depends(get_session)):
    if db.get(ResearchSession, session_id) is None:
        raise _missing("research_session")
    rows = db.scalars(select(ResearchSource).where(ResearchSource.session_id == session_id).order_by(ResearchSource.id).offset((page-1)*page_size).limit(page_size)).all()
    return rows


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: int, db: Session = Depends(get_session)):
    row = db.get(ResearchSource, source_id)
    if row is None:
        raise _missing("source")
    return row


@router.get("/research-sessions/{session_id}/claims", response_model=list[ClaimOut])
def list_claims(session_id: int, db: Session = Depends(get_session)):
    if db.get(ResearchSession, session_id) is None:
        raise _missing("research_session")
    rows = db.scalars(select(Claim).where(Claim.session_id == session_id).options(selectinload(Claim.source_links).selectinload(ClaimSource.source)).order_by(Claim.id)).all()
    return [_claim_out(x) for x in rows]


@router.patch("/claims/{claim_id}", response_model=ClaimOut)
def review_claim(claim_id: int, payload: ClaimReview, db: Session = Depends(get_session)):
    row = db.scalar(select(Claim).where(Claim.id == claim_id).options(selectinload(Claim.source_links).selectinload(ClaimSource.source)))
    if row is None:
        raise _missing("claim")
    data = payload.model_dump(exclude_unset=True)
    if data.get("verification_status"):
        row.verification_status = data["verification_status"]
    if "reviewer_notes" in data:
        row.reviewer_notes = data["reviewer_notes"]
    db.commit()
    db.refresh(row)
    return _claim_out(row)


@router.post("/claims/{claim_id}/fact-check")
def fact_check_claim(claim_id: int, db: Session = Depends(get_session)):
    row = db.scalar(select(Claim).where(Claim.id == claim_id).options(selectinload(Claim.source_links).selectinload(ClaimSource.source)))
    if row is None:
        raise _missing("claim")
    evidence = [{"title": link.source.title, "url": link.source.url, "excerpt": link.evidence or link.source.summary or ""} for link in row.source_links]
    if not evidence:
        result = {"suggested_status": "insufficient_evidence", "supporting_evidence": [], "contradicting_evidence": [], "confidence": 0.0}
        method = "no_linked_sources"
    else:
        try:
            result = configured_ai_provider().generate_json(system="Assess whether supplied excerpts support or contradict the claim. Do not invent evidence. Return JSON with suggested_status among supported, partially_supported, disputed, contradicted, insufficient_evidence; confidence number 0..1; supporting_evidence array; contradicting_evidence array. This is an AI suggestion, not verified fact.", prompt=f"Claim: {row.text}\nEvidence: {evidence}")
        except ProviderUnavailable as exc:
            raise HTTPException(503, {"code": "provider_unavailable", "message": str(exc)}) from exc
        method = "ai_assisted_suggestion"
    status = result.get("suggested_status", "insufficient_evidence")
    allowed = {"supported", "partially_supported", "disputed", "contradicted", "insufficient_evidence"}
    if status not in allowed:
        status = "insufficient_evidence"
    confidence = result.get("confidence")
    if not isinstance(confidence, (float, int)) or not 0 <= confidence <= 1:
        confidence = None
    supporting = result.get("supporting_evidence", [])
    contradicting = result.get("contradicting_evidence", [])
    check = FactCheckResult(claim_id=row.id, status=status, confidence=confidence,
        supporting_evidence=supporting[:30] if isinstance(supporting, list) else [], contradicting_evidence=contradicting[:30] if isinstance(contradicting, list) else [], method=method)
    db.add(check)
    # Deliberately leave the claim unverified until a reviewer changes its status.
    db.commit()
    db.refresh(check)
    return {"id": check.id, "claim_id": check.claim_id, "suggested_status": check.status, "confidence": check.confidence,
            "supporting_evidence": check.supporting_evidence, "contradicting_evidence": check.contradicting_evidence,
            "method": check.method, "created_at": _date(check.created_at), "review_required": True}


@router.get("/claims/{claim_id}/fact-check-results")
def fact_check_results(claim_id: int, db: Session = Depends(get_session)):
    if db.get(Claim, claim_id) is None:
        raise _missing("claim")
    rows = db.scalars(select(FactCheckResult).where(FactCheckResult.claim_id == claim_id).order_by(FactCheckResult.id.desc()).limit(50)).all()
    return [{"id": x.id, "suggested_status": x.status, "confidence": x.confidence, "supporting_evidence": x.supporting_evidence,
             "contradicting_evidence": x.contradicting_evidence, "method": x.method, "created_at": _date(x.created_at), "review_required": True} for x in rows]


@router.post("/projects/{project_id}/scripts", status_code=201)
def generate_script(project_id: int, payload: ScriptGenerate, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    if project is None:
        raise _missing("project")
    research = db.get(ResearchSession, payload.research_session_id) if payload.research_session_id else None
    if payload.research_session_id and (research is None or research.project_id != project_id):
        raise _missing("research_session")
    claims = []
    if research:
        claims = db.scalars(select(Claim).where(Claim.session_id == research.id).order_by(Claim.id).limit(100)).all()
    try:
        output = configured_ai_provider().generate_json(system="Write a structured documentary video script in JSON. Return sections object with keys hook, introduction, historical_background, main_developments, turning_points, geopolitical_implications, conclusion. Treat all supplied claims as unverified unless their review status says otherwise. Preserve attribution and qualify disputes. Do not invent source citations or factual details. Keep sections suitable for spoken narration.",
            prompt=f"Project topic: {project.topic or (research.topic if research else '')}\nDuration seconds: {project.target_duration_seconds}\nLanguage: {project.language}\nVisual style: {project.visual_style}\nAspect ratio: {project.aspect_ratio}\nAudience: {payload.audience}\nNarrative structure: {payload.narrative_structure}\nResearch overview: {research.results.get('overview','') if research else 'No research provided'}\nClaims: {[{'text': c.text, 'category': c.category, 'review_status': c.verification_status, 'sources': [l.source.url for l in c.source_links]} for c in claims]}")
    except ProviderUnavailable as exc:
        raise HTTPException(503, {"code": "provider_unavailable", "message": str(exc)}) from exc
    sections = clean_script_sections(output)
    doc = ScriptDocument(project_id=project_id, research_session_id=research.id if research else None, title=f"{project.name} script")
    doc.sections = [ScriptSection(**section) for section in sections]
    db.add(doc)
    db.flush()
    _snapshot(db, doc, "Generated script")
    db.commit()
    return _script_out(_load_script(db, doc.id))


@router.get("/projects/{project_id}/scripts")
def list_scripts(project_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_session)):
    if db.get(Project, project_id) is None:
        raise _missing("project")
    rows = db.scalars(select(ScriptDocument).where(ScriptDocument.project_id == project_id).options(selectinload(ScriptDocument.sections)).order_by(ScriptDocument.updated_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return [_script_out(x) for x in rows]


@router.get("/scripts/{script_id}")
def get_script(script_id: int, db: Session = Depends(get_session)):
    return _script_out(_load_script(db, script_id))


@router.patch("/scripts/{script_id}/sections/{section_key}")
def update_section(script_id: int, section_key: str, payload: SectionUpdate, db: Session = Depends(get_session)):
    script = _load_script(db, script_id)
    section = next((x for x in script.sections if x.section_key == section_key), None)
    if section is None:
        raise _missing("script_section")
    _snapshot(db, script, payload.change_note)
    section.content = payload.content
    section.approved = False
    _clear_section_narration(db, script.id, section_key)
    script.updated_at = datetime.now(UTC)
    db.commit()
    return _script_out(_load_script(db, script_id))


@router.patch("/scripts/{script_id}/sections/{section_key}/approval")
def approve_section(script_id: int, section_key: str, payload: SectionApproval, db: Session = Depends(get_session)):
    script = _load_script(db, script_id)
    section = next((x for x in script.sections if x.section_key == section_key), None)
    if section is None:
        raise _missing("script_section")
    section.approved = payload.approved
    if not payload.approved:
        _clear_section_narration(db, script.id, section_key)
    db.commit()
    return {"script_id": script.id, "section_key": section.section_key, "approved": section.approved}


@router.post("/scripts/{script_id}/sections/{section_key}/regenerate")
def regenerate_section(script_id: int, section_key: str, db: Session = Depends(get_session)):
    script = _load_script(db, script_id)
    section = next((x for x in script.sections if x.section_key == section_key), None)
    if section is None:
        raise _missing("script_section")
    if section_key not in {key for key, _ in SECTION_ORDER}:
        raise HTTPException(422, {"code": "invalid_section", "message": "This script section cannot be regenerated."})
    project = db.get(Project, script.project_id)
    try:
        result = configured_ai_provider().generate_json(system="Return JSON with a single string field named content. Write only the requested documentary script section, grounded in the supplied brief. Clearly qualify disputed facts and do not invent citations.", prompt=f"Section: {section.title}\nTopic: {project.topic}\nLanguage: {project.language}\nDuration: {project.target_duration_seconds}\nCurrent section: {section.content}")
    except ProviderUnavailable as exc:
        raise HTTPException(503, {"code": "provider_unavailable", "message": str(exc)}) from exc
    text = result.get("content")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(502, {"code": "invalid_provider_response", "message": "The AI provider returned an empty section."})
    _snapshot(db, script, f"Regenerated {section.title}")
    section.content = text[:12000]
    section.approved = False
    _clear_section_narration(db, script.id, section_key)
    script.updated_at = datetime.now(UTC)
    db.commit()
    return _script_out(_load_script(db, script_id))


@router.get("/scripts/{script_id}/versions")
def list_versions(script_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_session)):
    if db.get(ScriptDocument, script_id) is None:
        raise _missing("script")
    rows = db.scalars(select(ScriptVersion).where(ScriptVersion.script_id == script_id).order_by(ScriptVersion.version_number.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return [{"id": x.id, "version_number": x.version_number, "sections": x.sections_snapshot, "change_note": x.change_note, "created_at": _date(x.created_at)} for x in rows]


@router.post("/scripts/{script_id}/storyboards", status_code=201)
def generate_storyboard(script_id: int, db: Session = Depends(get_session)):
    script = _load_script(db, script_id)
    project = db.get(Project, script.project_id)
    claim_rows = db.scalars(select(Claim).where(Claim.session_id == script.research_session_id).order_by(Claim.id).limit(100)).all() if script.research_session_id else []
    source_rows = db.scalars(select(ResearchSource).where(ResearchSource.session_id == script.research_session_id).order_by(ResearchSource.id).limit(100)).all() if script.research_session_id else []
    allowed_claims = {claim.id for claim in claim_rows}
    allowed_sources = {source.id for source in source_rows}
    allowed_sections = {section.section_key for section in script.sections}
    try:
        result = configured_ai_provider().generate_json(system="Convert the script into a storyboard. Return JSON with scenes array, 1 to 100 items. Each scene has title, script_section_key (one of the supplied keys), narration_text, description, duration_seconds (integer), visual_direction, historical_events (array), geographic_references (array), claim_ids (array of integer IDs from supplied claims only), source_ids (array of integer IDs from supplied sources only), transition_suggestion. Do not fabricate facts or reference IDs. Preserve narrative order.", prompt=f"Project {project.name}; aspect ratio {project.aspect_ratio}; style {project.visual_style}. Script sections and keys: {[{'key': x.section_key, 'title': x.title, 'content': x.content} for x in script.sections]}. Available researched claims (IDs and review statuses): {[{'id': c.id, 'text': c.text, 'status': c.verification_status} for c in claim_rows]}. Available research sources (IDs and URLs): {[{'id': s.id, 'title': s.title, 'url': s.url} for s in source_rows]}")
    except ProviderUnavailable as exc:
        raise HTTPException(503, {"code": "provider_unavailable", "message": str(exc)}) from exc
    raw_scenes = result.get("scenes")
    if not isinstance(raw_scenes, list) or not 1 <= len(raw_scenes) <= 100:
        raise HTTPException(502, {"code": "invalid_storyboard", "message": "The AI provider returned an invalid storyboard."})
    board = Storyboard(script_id=script.id, schema_version="1.1")
    for index, raw in enumerate(raw_scenes, start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("title"), str):
            raise HTTPException(502, {"code": "invalid_storyboard", "message": "A storyboard scene is missing its title."})
        duration = raw.get("duration_seconds", 20)
        if not isinstance(duration, int) or not 1 <= duration <= 600:
            duration = 20
        section_key = raw.get("script_section_key") if raw.get("script_section_key") in allowed_sections else None
        claim_ids = raw.get("claim_ids", []) if isinstance(raw.get("claim_ids", []), list) else []
        source_ids = raw.get("source_ids", []) if isinstance(raw.get("source_ids", []), list) else []
        board.scenes.append(StoryboardScene(scene_number=index, title=raw["title"][:200], script_section_key=section_key, narration_text=str(raw.get("narration_text", ""))[:12000],
            description=str(raw.get("description", ""))[:8000], duration_seconds=duration, visual_direction=str(raw.get("visual_direction", ""))[:8000],
            historical_events=[str(x)[:1000] for x in raw.get("historical_events", [])[:20] if isinstance(x, (str, int, float))] if isinstance(raw.get("historical_events", []), list) else [],
            geographic_references=[str(x)[:1000] for x in raw.get("geographic_references", [])[:20] if isinstance(x, (str, int, float))] if isinstance(raw.get("geographic_references", []), list) else [],
            claim_ids=[value for value in claim_ids if type(value) is int and value in allowed_claims][:50], source_ids=[value for value in source_ids if type(value) is int and value in allowed_sources][:50], transition_suggestion=str(raw.get("transition_suggestion", ""))[:300] or None))
    db.add(board)
    db.commit()
    db.refresh(board)
    return {"id": board.id, "script_id": script.id, "schema_version": board.schema_version, "scenes": [_scene_out(x) for x in board.scenes]}


@router.get("/scripts/{script_id}/storyboards")
def list_storyboards(script_id: int, db: Session = Depends(get_session)):
    if db.get(ScriptDocument, script_id) is None:
        raise _missing("script")
    boards = db.scalars(select(Storyboard).where(Storyboard.script_id == script_id).options(selectinload(Storyboard.scenes)).order_by(Storyboard.id.desc()).limit(20)).all()
    return [{"id": x.id, "script_id": x.script_id, "schema_version": x.schema_version, "scenes": [_scene_out(s) for s in x.scenes]} for x in boards]


@router.patch("/storyboard-scenes/{scene_id}")
def update_scene(scene_id: int, payload: SceneUpdate, db: Session = Depends(get_session)):
    scene = db.get(StoryboardScene, scene_id)
    if scene is None:
        raise _missing("storyboard_scene")
    board = db.get(Storyboard, scene.storyboard_id)
    script = db.get(ScriptDocument, board.script_id) if board else None
    research_id = script.research_session_id if script else None
    allowed_claims = set(db.scalars(select(Claim.id).where(Claim.session_id == research_id)).all()) if research_id else set()
    allowed_sources = set(db.scalars(select(ResearchSource.id).where(ResearchSource.session_id == research_id)).all()) if research_id else set()
    if not set(payload.claim_ids).issubset(allowed_claims) or not set(payload.source_ids).issubset(allowed_sources):
        raise HTTPException(422, {"code": "invalid_scene_references", "message": "Scene references must belong to this project's selected research session."})
    valid_section_keys = {section.section_key for section in script.sections} if script else set()
    if payload.script_section_key is not None and payload.script_section_key not in valid_section_keys:
        raise HTTPException(422, {"code": "invalid_script_section", "message": "Scene must reference a section from its script."})
    for key, value in payload.model_dump().items():
        setattr(scene, key, value)
    db.commit()
    db.refresh(scene)
    return _scene_out(scene)


@router.post("/storyboards/{storyboard_id}/narration")
def prepare_narration(storyboard_id: int, config: NarrationConfig, db: Session = Depends(get_session)):
    board = db.scalar(select(Storyboard).where(Storyboard.id == storyboard_id).options(selectinload(Storyboard.scenes)))
    if board is None:
        raise _missing("storyboard")
    script = db.get(ScriptDocument, board.script_id)
    approved_keys = {section.section_key for section in script.sections if section.approved} if script else set()
    eligible_scenes = [scene for scene in board.scenes if scene.script_section_key in approved_keys]
    if not eligible_scenes:
        raise HTTPException(409, {"code": "approved_script_required", "message": "Approve at least one script section, then generate or update scenes linked to that section before preparing narration."})
    output = []
    for scene in board.scenes:
        for segment in list(scene.narration_segments):
            db.delete(segment)
        if scene.script_section_key not in approved_keys:
            continue
        segments = segment_narration(scene.narration_text)
        for index, segment in enumerate(segments, 1):
            text = segment["text"]
            duration = max(0.1, len(text.split()) / config.words_per_minute * 60)
            row = NarrationSegment(scene_id=scene.id, segment_number=index, paragraph_number=segment["paragraph_number"], text=text, estimated_duration_seconds=round(duration, 2))
            db.add(row)
            db.flush()
            output.append({"id": row.id, "scene_id": scene.id, "scene_number": scene.scene_number, "segment_number": index, "paragraph_number": segment["paragraph_number"], "text": text, "estimated_duration_seconds": round(duration, 2)})
    db.commit()
    return {"storyboard_id": board.id, "words_per_minute": config.words_per_minute, "segments": output}


@router.get("/storyboards/{storyboard_id}/narration")
def list_narration(storyboard_id: int, db: Session = Depends(get_session)):
    if db.get(Storyboard, storyboard_id) is None:
        raise _missing("storyboard")
    rows = db.scalars(select(NarrationSegment).join(StoryboardScene).where(StoryboardScene.storyboard_id == storyboard_id).order_by(StoryboardScene.scene_number, NarrationSegment.segment_number)).all()
    return [{"id": x.id, "scene_id": x.scene_id, "segment_number": x.segment_number, "paragraph_number": x.paragraph_number, "text": x.text, "estimated_duration_seconds": x.estimated_duration_seconds} for x in rows]


@router.patch("/narration-segments/{segment_id}")
def update_narration(segment_id: int, payload: NarrationSegmentUpdate, db: Session = Depends(get_session)):
    row = db.get(NarrationSegment, segment_id)
    if row is None:
        raise _missing("narration_segment")
    row.text = payload.text
    row.estimated_duration_seconds = round(max(0.1, len(payload.text.split()) / payload.words_per_minute * 60), 2)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "scene_id": row.scene_id, "segment_number": row.segment_number, "paragraph_number": row.paragraph_number, "text": row.text, "estimated_duration_seconds": row.estimated_duration_seconds}
