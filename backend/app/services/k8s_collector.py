import asyncio
import subprocess
import json
from typing import List, Optional
from app.core.config import settings
from app.models.log import K8sResource, LogEntry
from sqlalchemy.orm import Session


class K8sLogCollector:
    """Collect logs from Kubernetes cluster using kubectl commands."""
    
    def __init__(self):
        self.k8s_available = self._check_kubectl_available()
        if self.k8s_available:
            print("kubectl command available for Kubernetes operations")
        else:
            print("kubectl command not available, Kubernetes features disabled")
    
    def _check_kubectl_available(self) -> bool:
        """Check if kubectl command is available."""
        try:
            result = subprocess.run(['kubectl', 'version', '--client'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _run_kubectl_command(self, command: List[str]) -> str:
        """Run a kubectl command and return output."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                print(f"kubectl command failed: {result.stderr}")
                return ""
            return result.stdout
        except subprocess.TimeoutExpired:
            print("kubectl command timed out")
            return ""
        except Exception as e:
            print(f"Error running kubectl command: {e}")
            return ""
    
    def get_namespaces(self) -> List[str]:
        """Get all namespaces using kubectl."""
        if not self.k8s_available:
            return []
        
        try:
            output = self._run_kubectl_command(['kubectl', 'get', 'namespaces', '-o', 'jsonpath={.items[*].metadata.name}'])
            if output:
                namespaces = output.split()
                return namespaces
            return []
        except Exception as e:
            print(f"Error fetching namespaces: {e}")
            return []
    
    def get_pods(self, namespace: str = "default") -> List[dict]:
        """Get all pods in a namespace using kubectl."""
        if not self.k8s_available:
            return []
        
        try:
            output = self._run_kubectl_command([
                'kubectl', 'get', 'pods', '-n', namespace,
                '-o', 'json'
            ])
            
            if not output:
                return []
            
            data = json.loads(output)
            pods = []
            
            for item in data.get('items', []):
                pod_name = item.get('metadata', {}).get('name', '')
                status = item.get('status', {}).get('phase', 'Unknown')
                containers = [c.get('name', '') for c in item.get('spec', {}).get('containers', [])]
                created = item.get('metadata', {}).get('creationTimestamp', None)
                
                pods.append({
                    'name': pod_name,
                    'namespace': namespace,
                    'status': status,
                    'containers': containers,
                    'created': created
                })
            
            return pods
        except Exception as e:
            print(f"Error fetching pods in {namespace}: {e}")
            return []
    
    def get_pod_logs(
        self, 
        namespace: str, 
        pod_name: str, 
        container: Optional[str] = None,
        tail_lines: int = 100
    ) -> str:
        """Get logs from a specific pod using kubectl."""
        if not self.k8s_available:
            return ""
        
        try:
            command = ['kubectl', 'logs', pod_name, '-n', namespace, '--tail', str(tail_lines)]
            if container:
                command.extend(['-c', container])
            
            logs = self._run_kubectl_command(command)
            return logs
        except Exception as e:
            print(f"Error fetching logs for {pod_name}: {e}")
            return ""
    
    def collect_all_logs(self, db: Session, namespaces: Optional[List[str]] = None):
        """Collect logs from all pods in specified namespaces using kubectl."""
        if not self.k8s_available:
            print("kubectl not available, skipping log collection")
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
                        print(f"Collected {len(logs)} bytes from {namespace}/{pod_name}/{container}")
    
    def get_cluster_health(self) -> dict:
        """Get overall cluster health summary using kubectl."""
        if not self.k8s_available:
            return {"status": "unavailable", "error": "kubectl not available"}
        
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
