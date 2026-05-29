from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.database import get_db
from app.models.log import LogEntry, K8sResource, LogAnalysis, LogSession
from app.models.schemas import (
    LogEntryResponse,
    LogUploadResponse,
    LogAnalysisRequest,
    LogAnalysisResponse,
    K8sResourceResponse,
    LogSessionResponse
)
from app.services.log_parser import LogParser
from app.services.llm_analyzer import LLMLogAnalyzer

router = APIRouter()
log_parser = LogParser()
llm_analyzer = LLMLogAnalyzer()


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
        
        # Trigger analysis (with error handling)
        try:
            analysis = llm_analyzer.analyze_logs(parsed_entries)
            
            # Store analysis
            log_analysis = LogAnalysis(
                resource_id=resource.id,
                source_file=file.filename,
                analysis_type="upload",
                findings={"anomalies": analysis.get("anomalies", [])},
                suggestions=analysis
            )
            db.add(log_analysis)
            db.commit()
            db.refresh(log_analysis)

            # Auto-create session for uploaded file
            severity = analysis.get('severity', None)
            session = LogSession(
                name=file.filename,
                source_type='file',
                resource_id=resource.id,
                analysis_id=log_analysis.id,
                entry_count=entries_created,
                severity=severity
            )
            db.add(session)
            db.commit()

            analysis_id = log_analysis.id
        except Exception as analysis_error:
            print(f"Analysis failed during upload: {analysis_error}")
            analysis_id = None
            # Don't rollback - file upload should succeed even if analysis fails
        
        return LogUploadResponse(
            message="Log file uploaded and analyzed successfully",
            file_id=resource.id,
            entries_count=entries_created,
            analysis_id=analysis_id
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


@router.post("/analyze", response_model=LogAnalysisResponse)
def analyze_logs(
    request: LogAnalysisRequest,
    db: Session = Depends(get_db)
):
    """Trigger LLM analysis for logs from a specific resource."""
    try:
        # Fetch log entries
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
        
        # Convert to dict format for analyzer
        log_dicts = [
            {
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
                'level': entry.level.value if entry.level else None,
                'message': entry.message,
                'raw_log': entry.raw_log
            }
            for entry in log_entries
        ]
        
        # Run analysis
        analysis = llm_analyzer.analyze_logs(log_dicts, request.analysis_type)
        
        # Store analysis
        log_analysis = LogAnalysis(
            resource_id=request.resource_id,
            source_file=request.source_file,
            analysis_type=request.analysis_type,
            findings={"anomalies": analysis.get("anomalies", [])},
            suggestions=analysis
        )
        db.add(log_analysis)
        db.commit()
        db.refresh(log_analysis)

        # Determine severity and auto-create session
        severity = analysis.get('severity', None)
        resource_name = (
            db.query(K8sResource).filter(K8sResource.id == request.resource_id).first().pod_name
            if request.resource_id
            else (request.source_file or 'Unknown')
        )
        session = LogSession(
            name=resource_name,
            source_type='pod' if request.resource_id else 'file',
            resource_id=request.resource_id,
            analysis_id=log_analysis.id,
            entry_count=len(log_entries),
            severity=severity
        )
        db.add(session)
        db.commit()

        return log_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
