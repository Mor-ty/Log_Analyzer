from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.database import get_db, SessionLocal
from app.models.log import LogEntry, K8sResource, LogAnalysis, LogSession
from app.models.schemas import (
    LogEntryResponse,
    LogUploadResponse,
    LogAnalysisRequest,
    LogAnalysisResponse,
    AnalysisJobResponse,
    K8sResourceResponse,
    LogSessionResponse
)
from app.services.log_parser import LogParser
from app.services.llm_analyzer import LLMLogAnalyzer
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()
log_parser = LogParser()
llm_analyzer = LLMLogAnalyzer()

# ── Async job infrastructure ───────────────────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=4)
_jobs: dict = {}  # job_id -> {status, result, error, analysis_id}


def _run_analysis_job(
    job_id: str,
    log_dicts: list,
    resource_id: Optional[int],
    source_file: Optional[str],
    analysis_type: str,
):
    """Blocking analysis task — runs in a thread pool with its own DB session."""
    db = SessionLocal()
    try:
        _jobs[job_id]["status"] = "running"
        analysis = llm_analyzer.analyze_logs(log_dicts, analysis_type)

        log_analysis = LogAnalysis(
            resource_id=resource_id,
            source_file=source_file,
            analysis_type=analysis_type,
            findings={"anomalies": analysis.get("anomalies", [])},
            suggestions=analysis,
        )
        db.add(log_analysis)
        db.commit()
        db.refresh(log_analysis)

        # Auto-create session
        severity = analysis.get("severity")
        resource_name = source_file or "Unknown"
        if resource_id:
            r = db.query(K8sResource).filter(K8sResource.id == resource_id).first()
            if r:
                resource_name = r.pod_name
        session = LogSession(
            name=resource_name,
            source_type="pod" if resource_id else "file",
            resource_id=resource_id,
            analysis_id=log_analysis.id,
            entry_count=len(log_dicts),
            severity=severity,
        )
        db.add(session)
        db.commit()

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["analysis_id"] = log_analysis.id
        # Serialise result for polling response
        import json as _json
        findings = log_analysis.findings
        suggestions = log_analysis.suggestions
        if isinstance(findings, str):
            findings = _json.loads(findings)
        if isinstance(suggestions, str):
            suggestions = _json.loads(suggestions)
        _jobs[job_id]["result"] = {
            "id": log_analysis.id,
            "resource_id": resource_id,
            "source_file": source_file,
            "analysis_type": analysis_type,
            "findings": findings,
            "suggestions": suggestions,
            "created_at": log_analysis.created_at.isoformat(),
        }
    except Exception as exc:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        print(f"[job {job_id}] Analysis failed: {exc}")
    finally:
        db.close()


@router.post("/upload", response_model=LogUploadResponse)
async def upload_log_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a log file for processing and analysis."""
    try:
        content = await file.read()
        
        # Try to decode as UTF-8, fallback to latin-1 if that fails
        try:
            log_content = content.decode('utf-8')
        except UnicodeDecodeError:
            log_content = content.decode('latin-1')
        
        # Parse the log file
        parsed_entries = log_parser.parse_file(log_content)
        
        if not parsed_entries:
            raise HTTPException(status_code=400, detail="No valid log entries found")
        
        # Check if file with same name already exists (deduplication)
        existing_resource = db.query(K8sResource).filter(
            K8sResource.pod_name == file.filename,
            K8sResource.resource_type == "file"
        ).first()
        
        if existing_resource:
            # File already uploaded, return existing resource info
            # Check if there's existing analysis
            existing_analysis = db.query(LogAnalysis).filter(
                LogAnalysis.resource_id == existing_resource.id
            ).first()
            
            analysis_id = existing_analysis.id if existing_analysis else None
            
            return LogUploadResponse(
                message="File already exists. Using existing data.",
                file_id=existing_resource.id,
                entries_count=db.query(LogEntry).filter(LogEntry.resource_id == existing_resource.id).count(),
                analysis_id=analysis_id
            )
        
        # Store log entries for new file
        resource = K8sResource(
            namespace="uploaded",
            pod_name=file.filename,
            resource_type="file"
        )
        db.add(resource)
        db.commit()
        db.refresh(resource)
        
        entries_created = 0
        for entry in parsed_entries:
            log_entry = LogEntry(
                resource_id=resource.id,
                timestamp=entry.get('timestamp'),
                level=entry.get('level'),
                message=entry.get('message'),
                raw_log=entry.get('message'),
                source_file=file.filename
            )
            db.add(log_entry)
            entries_created += 1
        
        db.commit()
        
        # Start analysis in background — does NOT block the upload response
        log_dicts = [
            {
                'timestamp': e.get('timestamp'),
                'level': str(e.get('level', '')),
                'message': e.get('message', ''),
                'raw_log': e.get('message', ''),
            }
            for e in parsed_entries
        ]
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {"status": "pending", "result": None, "error": None, "analysis_id": None}
        loop = asyncio.get_event_loop()
        loop.run_in_executor(_executor, _run_analysis_job, job_id, log_dicts, resource.id, file.filename, "upload")
        
        return LogUploadResponse(
            message="Log file uploaded — analysis running in background",
            file_id=resource.id,
            entries_count=entries_created,
            job_id=job_id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/entries", response_model=List[LogEntryResponse])
def get_log_entries(
    resource_id: Optional[int] = None,
    level: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve log entries with optional filters."""
    query = db.query(LogEntry)
    
    if resource_id:
        query = query.filter(LogEntry.resource_id == resource_id)
    
    if level:
        query = query.filter(LogEntry.level == level)
    
    entries = query.order_by(LogEntry.timestamp.desc()).limit(limit).all()
    return entries


@router.get("/resources", response_model=List[K8sResourceResponse])
def get_resources(db: Session = Depends(get_db)):
    """Get all available resources (pods, uploaded files, etc.)."""
    resources = db.query(K8sResource).all()
    return resources


@router.post("/analyze", response_model=AnalysisJobResponse)
async def analyze_logs(
    request: LogAnalysisRequest,
    db: Session = Depends(get_db)
):
    """Start async LLM analysis — returns a job_id to poll for results."""
    try:
        query = db.query(LogEntry)
        if request.resource_id:
            query = query.filter(LogEntry.resource_id == request.resource_id)
        elif request.source_file:
            query = query.filter(LogEntry.source_file == request.source_file)
        else:
            raise HTTPException(status_code=400, detail="Either resource_id or source_file must be provided")

        log_entries = query.all()
        if not log_entries:
            raise HTTPException(status_code=404, detail="No log entries found")

        log_dicts = [
            {
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
                'level': entry.level.value if entry.level else None,
                'message': entry.message,
                'raw_log': entry.raw_log,
            }
            for entry in log_entries
        ]

        job_id = str(uuid.uuid4())
        _jobs[job_id] = {"status": "pending", "result": None, "error": None, "analysis_id": None}
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            _executor, _run_analysis_job,
            job_id, log_dicts, request.resource_id, request.source_file, request.analysis_type
        )

        return AnalysisJobResponse(job_id=job_id, status="pending")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
def get_job_status(job_id: str):
    """Poll an async analysis job for its current status and result."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    result = None
    if job.get("result"):
        result = LogAnalysisResponse(**job["result"])
    return AnalysisJobResponse(
        job_id=job_id,
        status=job["status"],
        result=result,
        error=job.get("error"),
    )


@router.get("/analysis/{analysis_id}", response_model=LogAnalysisResponse)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific analysis result."""
    analysis = db.query(LogAnalysis).filter(LogAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    """Delete a resource and all its associated log entries and analyses."""
    resource = db.query(K8sResource).filter(K8sResource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    db.query(LogSession).filter(LogSession.resource_id == resource_id).delete()
    db.query(LogAnalysis).filter(LogAnalysis.resource_id == resource_id).delete()
    db.query(LogEntry).filter(LogEntry.resource_id == resource_id).delete()
    db.delete(resource)
    db.commit()
    return {"message": "Resource deleted successfully"}


# ── Session endpoints ──────────────────────────────────────────────────────────

@router.get("/sessions", response_model=List[LogSessionResponse])
def get_sessions(db: Session = Depends(get_db)):
    """List all log analysis sessions, newest first."""
    sessions = (
        db.query(LogSession)
        .order_by(LogSession.created_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        analysis = None
        if s.analysis_id:
            analysis = db.query(LogAnalysis).filter(LogAnalysis.id == s.analysis_id).first()
        item = LogSessionResponse(
            id=s.id,
            name=s.name,
            source_type=s.source_type,
            resource_id=s.resource_id,
            analysis_id=s.analysis_id,
            entry_count=s.entry_count,
            severity=s.severity,
            created_at=s.created_at,
            analysis=LogAnalysisResponse.model_validate(analysis) if analysis else None
        )
        result.append(item)
    return result


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Delete a session record (does not delete logs or resource)."""
    session = db.query(LogSession).filter(LogSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}
