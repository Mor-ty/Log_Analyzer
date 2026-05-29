from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import json


class LogEntryCreate(BaseModel):
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    message: str
    raw_log: str
    resource_id: Optional[int] = None
    source_file: Optional[str] = None


class LogEntryResponse(BaseModel):
    id: int
    timestamp: Optional[datetime]
    level: Optional[str]
    message: str
    raw_log: str
    resource_id: Optional[int]
    source_file: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class K8sResourceCreate(BaseModel):
    namespace: str
    pod_name: str
    container_name: Optional[str] = None
    resource_type: str = "pod"


class K8sResourceResponse(BaseModel):
    id: int
    namespace: str
    pod_name: str
    container_name: Optional[str]
    resource_type: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LogAnalysisRequest(BaseModel):
    resource_id: Optional[int] = None
    source_file: Optional[str] = None
    analysis_type: str = "general"


class LogAnalysisResponse(BaseModel):
    id: int
    resource_id: Optional[int]
    source_file: Optional[str]
    analysis_type: str
    findings: Dict[str, Any]
    suggestions: Dict[str, Any]
    created_at: datetime
    
    @field_validator('findings', 'suggestions', mode='before')
    @classmethod
    def parse_json_string(cls, v: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v
    
    class Config:
        from_attributes = True


class LogUploadResponse(BaseModel):
    message: str
    file_id: int
    entries_count: int
    analysis_id: Optional[int] = None


class K8sPodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    containers: List[str]
    created: Optional[str]


class LogSessionResponse(BaseModel):
    id: int
    name: str
    source_type: str
    resource_id: Optional[int]
    analysis_id: Optional[int]
    entry_count: int
    severity: Optional[str]
    created_at: datetime
    analysis: Optional['LogAnalysisResponse'] = None

    class Config:
        from_attributes = True


class ClusterHealthResponse(BaseModel):
    status: str
    namespaces: int
    total_pods: int
    running_pods: int
    failed_pods: int
    error: Optional[str] = None
