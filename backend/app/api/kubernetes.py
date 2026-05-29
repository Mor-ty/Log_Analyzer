from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.services.k8s_collector import collector
from app.services.log_parser import LogParser
from app.models.log import K8sResource, LogEntry
from app.models.schemas import K8sPodInfo, ClusterHealthResponse
import json

router = APIRouter()
log_parser = LogParser()


@router.get("/health", response_model=ClusterHealthResponse)
def get_cluster_health():
    """Get overall Kubernetes cluster health."""
    try:
        health = collector.get_cluster_health()
        return ClusterHealthResponse(**health)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces")
def get_namespaces():
    """Get all Kubernetes namespaces."""
    try:
        namespaces = collector.get_namespaces()
        return {"namespaces": namespaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pods/{namespace}", response_model=List[K8sPodInfo])
def get_pods(namespace: str):
    """Get all pods in a specific namespace."""
    try:
        pods = collector.get_pods(namespace)
        return [K8sPodInfo(**pod) for pod in pods]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{namespace}/{pod_name}")
def get_pod_logs(
    namespace: str,
    pod_name: str,
    container: Optional[str] = None,
    tail_lines: int = 100,
    store: bool = False,
    db: Session = Depends(get_db)
):
    """Get logs from a specific pod. Set store=true to persist to DB."""
    try:
        logs = collector.get_pod_logs(namespace, pod_name, container, tail_lines)

        if not logs:
            return {"logs": [], "message": "No logs found", "resource_id": None, "entries_count": 0, "raw_logs": ""}

        # Parse and structure the logs
        parsed_logs = log_parser.parse_k8s_log(logs, namespace, pod_name, container)

        if not store:
            # View-only: return parsed logs without touching the DB
            return {
                "logs": parsed_logs,
                "resource_id": None,
                "pod_name": pod_name,
                "namespace": namespace,
                "entries_count": len(parsed_logs),
                "raw_logs": logs
            }

        # store=True: persist resource + log entries to DB
        resource = db.query(K8sResource).filter_by(
            namespace=namespace,
            pod_name=pod_name
        ).first()

        if not resource:
            resource = K8sResource(
                namespace=namespace,
                pod_name=pod_name,
                container_name=container or 'main',
                resource_type='pod'
            )
            db.add(resource)
            db.commit()
            db.refresh(resource)

        # Store parsed logs
        entries_created = 0
        for entry in parsed_logs:
            log_entry = LogEntry(
                resource_id=resource.id,
                timestamp=entry.get('timestamp'),
                level=entry.get('level'),
                message=entry.get('message'),
                raw_log=entry.get('message')
            )
            db.add(log_entry)
            entries_created += 1

        db.commit()

        return {
            "logs": parsed_logs,
            "resource_id": resource.id,
            "pod_name": pod_name,
            "namespace": namespace,
            "entries_count": entries_created,
            "raw_logs": logs
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect-all")
def collect_all_logs(
    namespaces: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """Trigger log collection from all pods in specified namespaces."""
    try:
        collector.collect_all_logs(db, namespaces)
        return {"message": "Log collection started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
