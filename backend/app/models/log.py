from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class LogLevel(enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class K8sResource(Base):
    __tablename__ = "k8s_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    namespace = Column(String, index=True)
    pod_name = Column(String, index=True)
    container_name = Column(String, index=True)
    resource_type = Column(String)  # pod, service, deployment, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    logs = relationship("LogEntry", back_populates="resource", cascade="all, delete-orphan")


class LogEntry(Base):
    __tablename__ = "log_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("k8s_resources.id"), nullable=True)
    timestamp = Column(DateTime, index=True)
    level = Column(Enum(LogLevel))
    message = Column(Text)
    raw_log = Column(Text)
    source_file = Column(String, nullable=True)  # For uploaded files
    created_at = Column(DateTime, default=datetime.utcnow)
    
    resource = relationship("K8sResource", back_populates="logs")


class LogAnalysis(Base):
    __tablename__ = "log_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("k8s_resources.id"), nullable=True)
    source_file = Column(String, nullable=True)
    analysis_type = Column(String)  # "anomaly_detection", "error_analysis", etc.
    findings = Column(JSON, default=dict)  # JSON field for structured data
    suggestions = Column(JSON, default=dict)  # JSON field for structured data
    created_at = Column(DateTime, default=datetime.utcnow)


class LogSession(Base):
    __tablename__ = "log_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)          # display name (pod or filename)
    source_type = Column(String, default="file")   # "pod" or "file"
    resource_id = Column(Integer, ForeignKey("k8s_resources.id"), nullable=True)
    analysis_id = Column(Integer, ForeignKey("log_analyses.id"), nullable=True)
    entry_count = Column(Integer, default=0)
    severity = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
