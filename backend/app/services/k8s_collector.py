import asyncio
from typing import List, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app.core.config import settings
from app.models.log import K8sResource, LogEntry
from sqlalchemy.orm import Session


class K8sLogCollector:
    """Collect logs from Kubernetes cluster."""
    
    def __init__(self):
        self.k8s_loaded = False
        self.v1 = None
        self._load_k8s_config()
    
    def _load_k8s_config(self):
        """Load Kubernetes configuration."""
        try:
            if settings.KUBECONFIG:
                config.load_kube_config(config_file=settings.KUBECONFIG)
            else:
                # Try in-cluster config or default location
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config()
            
            self.v1 = client.CoreV1Api()
            self.k8s_loaded = True
            print("Kubernetes configuration loaded successfully")
        except Exception as e:
            print(f"Failed to load Kubernetes config: {e}")
            self.k8s_loaded = False
    
    def get_namespaces(self) -> List[str]:
        """Get all namespaces."""
        if not self.k8s_loaded:
            return []
        
        try:
            namespaces = self.v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except ApiException as e:
            print(f"Error fetching namespaces: {e}")
            return []
    
    def get_pods(self, namespace: str = "default") -> List[dict]:
        """Get all pods in a namespace."""
        if not self.k8s_loaded:
            return []
        
        try:
            pods = self.v1.list_namespaced_pod(namespace)
            return [
                {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'status': pod.status.phase,
                    'containers': [c.name for c in pod.spec.containers],
                    'created': pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
                }
                for pod in pods.items
            ]
        except ApiException as e:
            print(f"Error fetching pods in {namespace}: {e}")
            return []
    
    def get_pod_logs(
        self, 
        namespace: str, 
        pod_name: str, 
        container: Optional[str] = None,
        tail_lines: int = 100
    ) -> str:
        """Get logs from a specific pod."""
        if not self.k8s_loaded:
            return ""
        
        try:
            logs = self.v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines
            )
            return logs
        except ApiException as e:
            print(f"Error fetching logs for {pod_name}: {e}")
            return ""
    
    def collect_all_logs(self, db: Session, namespaces: Optional[List[str]] = None):
        """Collect logs from all pods in specified namespaces."""
        if not self.k8s_loaded:
            print("Kubernetes not configured, skipping log collection")
            return
        
        target_namespaces = namespaces or self.get_namespaces()
        
        for namespace in target_namespaces:
            pods = self.get_pods(namespace)
            
            for pod in pods:
                pod_name = pod['name']
                
                # Get or create resource record
                resource = db.query(K8sResource).filter_by(
                    namespace=namespace,
                    pod_name=pod_name
                ).first()
                
                if not resource:
                    resource = K8sResource(
                        namespace=namespace,
                        pod_name=pod_name,
                        container_name=pod['containers'][0] if pod['containers'] else None,
                        resource_type='pod'
                    )
                    db.add(resource)
                    db.commit()
                    db.refresh(resource)
                
                # Collect logs for each container
                for container in pod['containers']:
                    logs = self.get_pod_logs(namespace, pod_name, container)
                    
                    if logs:
                        # Store logs (implementation depends on your parsing logic)
                        # This is a simplified version
                        print(f"Collected {len(logs)} bytes from {namespace}/{pod_name}/{container}")
    
    def get_cluster_health(self) -> dict:
        """Get overall cluster health summary."""
        if not self.k8s_loaded:
            return {"status": "unavailable", "error": "Kubernetes not configured"}
        
        try:
            namespaces = self.get_namespaces()
            total_pods = 0
            running_pods = 0
            failed_pods = 0
            
            for ns in namespaces:
                pods = self.get_pods(ns)
                total_pods += len(pods)
                running_pods += sum(1 for p in pods if p['status'] == 'Running')
                failed_pods += sum(1 for p in pods if p['status'] in ['Failed', 'CrashLoopBackOff'])
            
            return {
                "status": "healthy" if failed_pods == 0 else "degraded",
                "namespaces": len(namespaces),
                "total_pods": total_pods,
                "running_pods": running_pods,
                "failed_pods": failed_pods
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Singleton instance
collector = K8sLogCollector()
