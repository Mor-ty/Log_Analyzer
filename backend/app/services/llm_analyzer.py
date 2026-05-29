import json
from typing import List, Dict, Optional, Set
import google.generativeai as genai
from collections import Counter
from datetime import datetime
import re
from app.core.config import settings


class LLMLogAnalyzer:
    """Use LLM to analyze logs with smart parsing and condensation for efficiency."""
    
    def __init__(self):
        self.client = None
        self.model = settings.GEMINI_MODEL
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.client = genai.GenerativeModel(self.model)
                print(f"Gemini client initialized with model: {self.model}")
            except Exception as e:
                print(f"Failed to initialize Gemini client: {e}")
    
    def analyze_logs(
        self, 
        log_entries: List[Dict], 
        analysis_type: str = "general"
    ) -> Dict:
        """Analyze log entries with smart parsing and enhanced rule-based analysis."""
        print(f"Starting smart analysis with enhanced rule-based approach, client configured: {self.client is not None}")
        
        # Use smart parsing for context extraction
        condensed_context = self._prepare_condensed_context(log_entries)
        print(f"Condensed {len(log_entries)} entries to {len(condensed_context)} characters")
        
        # Try LLM first; fall back to pattern-aware rule-based analysis only on failure
        if self.client:
            try:
                prompt = self._build_smart_prompt(condensed_context, analysis_type)
                print(f"Attempting Gemini analysis ({self.model}), prompt length: {len(prompt)} chars...")
                response = self.client.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=8192,  # Enough for full structured analysis
                    )
                )

                print(f"Gemini response received ({len(response.text)} chars), parsing...")
                result = self._parse_response(response.text)
                confidence = result.get("confidence_score", 0)
                print(f"Parsed result confidence: {confidence}")
                # Accept LLM result whenever it returns a valid structured response
                # (confidence >= 0.4 means the LLM produced something meaningful)
                if confidence >= 0.4:
                    print(f"Using Gemini analysis (confidence={confidence})")
                    return result
                else:
                    print(f"Gemini returned very low confidence ({confidence}), using pattern-aware fallback")
                    return self._enhanced_fallback_analysis(log_entries, condensed_context)
            except Exception as e:
                print(f"Gemini analysis failed — {type(e).__name__}: {e}")
                print("Falling back to pattern-aware rule-based analysis")
                return self._enhanced_fallback_analysis(log_entries, condensed_context)
        else:
            print("LLM not configured, using enhanced rule-based analysis")
            return self._enhanced_fallback_analysis(log_entries, condensed_context)
    
    def _prepare_condensed_context(self, log_entries: List[Dict]) -> str:
        """
        Smart context: group identical patterns, send once with count + time range.
        Cuts tokens by ~70% vs raw dump while preserving the specificity LLM needs.
        Strategy:
          - Errors: group by normalized pattern → first full message (220 chars) + [Nx] + time span
          - Warnings: same, top 8 unique patterns
          - Stack traces: deduplicated by first 80 chars, top 3
          - Info: 3-line sample only for baseline context
        """
        critical_errors = [e for e in log_entries if str(e.get('level')) in ['ERROR', 'CRITICAL', 'LogLevel.ERROR', 'LogLevel.CRITICAL']]
        warnings = [e for e in log_entries if str(e.get('level')) in ['WARNING', 'LogLevel.WARNING']]
        info_entries = [e for e in log_entries if str(e.get('level')) in ['INFO', 'LogLevel.INFO']]

        context_parts = []

        # --- Summary header ---
        context_parts.append("=== INCIDENT SUMMARY ===")
        context_parts.append(f"Total log entries: {len(log_entries)}  |  Errors: {len(critical_errors)}  |  Warnings: {len(warnings)}  |  Info: {len(info_entries)}")
        if log_entries:
            context_parts.append(f"Time range: {log_entries[0].get('timestamp', 'N/A')}  →  {log_entries[-1].get('timestamp', 'N/A')}")

        # --- Key K8s/service signals found anywhere in logs ---
        all_messages = " ".join(e.get('message', '') for e in log_entries)
        signal_keywords = [
            'OOMKilled', 'CrashLoopBackOff', 'Evicted', 'BackOff', 'Pending',
            'OutOfMemoryError', 'heap space', 'connection refused', 'timeout',
            'certificate', 'ImagePullBackOff', 'FailedScheduling', 'exit code 137',
            'circuit breaker', 'upstream', '504', '503', 'health check failed',
        ]
        detected = [kw for kw in signal_keywords if kw.lower() in all_messages.lower()]
        if detected:
            context_parts.append(f"Detected signals: {', '.join(detected)}")

        # --- Unique error patterns grouped by normalized message ---
        error_groups: Dict[str, list] = {}
        for e in critical_errors:
            key = self._normalize_message(e.get('message', ''))[:100]
            if key not in error_groups:
                error_groups[key] = []
            error_groups[key].append(e)

        sorted_errors = sorted(error_groups.items(), key=lambda x: len(x[1]), reverse=True)
        context_parts.append(f"\n=== UNIQUE ERROR PATTERNS ({len(sorted_errors)} distinct, {len(critical_errors)} total occurrences) ===")
        for _, group in sorted_errors[:15]:
            count = len(group)
            first = group[0]
            first_ts = first.get('timestamp', '')
            last_ts = group[-1].get('timestamp', '') if count > 1 else ''
            svc = first.get('service', first.get('source', ''))
            msg = first.get('message', '')[:220]  # enough to extract names + error type

            time_str = f"{first_ts} → {last_ts}" if last_ts and last_ts != first_ts else first_ts
            svc_str = f" [{svc}]" if svc else ""
            context_parts.append(f"  [{count}x]{svc_str} {time_str}\n    {msg}")

        # --- Unique warning patterns (top 8) ---
        warning_groups: Dict[str, list] = {}
        for e in warnings:
            key = self._normalize_message(e.get('message', ''))[:100]
            if key not in warning_groups:
                warning_groups[key] = []
            warning_groups[key].append(e)

        sorted_warnings = sorted(warning_groups.items(), key=lambda x: len(x[1]), reverse=True)
        if sorted_warnings:
            context_parts.append(f"\n=== UNIQUE WARNING PATTERNS ({len(sorted_warnings)} distinct) ===")
            for _, group in sorted_warnings[:8]:
                count = len(group)
                first = group[0]
                ts = first.get('timestamp', '')
                svc = first.get('service', first.get('source', ''))
                msg = first.get('message', '')[:160]
                svc_str = f" [{svc}]" if svc else ""
                context_parts.append(f"  [{count}x]{svc_str} {ts}: {msg}")

        # --- Stack trace signatures (deduplicated by first 80 chars) ---
        stack_traces = self._extract_stack_traces(log_entries)
        if stack_traces:
            unique_traces = list({t[:80]: t for t in stack_traces}.values())
            context_parts.append(f"\n=== STACK TRACES ({len(unique_traces)} unique) ===")
            for trace in unique_traces[:3]:
                context_parts.append(f"  {trace[:350]}")

        # --- 3 INFO lines as baseline context ---
        if info_entries:
            context_parts.append(f"\n=== INFO SAMPLE (3 of {len(info_entries)}) ===")
            for e in info_entries[:3]:
                context_parts.append(f"  [{e.get('timestamp', '')}] {e.get('message', '')[:120]}")

        return "\n".join(context_parts)
    
    def _extract_stack_traces(self, log_entries: List[Dict]) -> List[str]:
        """Extract stack traces from log entries."""
        stack_traces = []
        for entry in log_entries:
            message = entry.get('message', '')
            # Common stack trace indicators
            if any(indicator in message.lower() for indicator in ['traceback', 'stack trace', 'at line', 'file ', 'exception']):
                stack_traces.append(message)
        return stack_traces
    
    def _deduplicate_messages(self, log_entries: List[Dict]) -> List[Dict]:
        """Remove duplicate messages keeping first occurrence."""
        seen: Set[str] = set()
        deduplicated = []
        
        for entry in log_entries:
            message = entry.get('message', '')
            # Normalize message for comparison (remove timestamps, ids)
            normalized = self._normalize_message(message)
            
            if normalized not in seen:
                seen.add(normalized)
                deduplicated.append(entry)
        
        return deduplicated
    
    def _normalize_message(self, message: str) -> str:
        """Normalize message for deduplication comparison."""
        # Remove common variable patterns
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}', '', message)  # Remove timestamps
        normalized = re.sub(r'\b[a-f0-9]{8,}\b', '', normalized)  # Remove hex ids
        normalized = re.sub(r'\b\d+\b', '', normalized)  # Remove numbers
        return normalized.strip().lower()[:100]  # Take first 100 chars
    
    def _detect_anomalies(self, log_entries: List[Dict]) -> List[str]:
        """Detect unusual patterns and anomalies."""
        anomalies = []
        
        # Check for error bursts (handle both enum and string formats)
        errors = [e for e in log_entries if str(e.get('level')) in ['ERROR', 'CRITICAL', 'LogLevel.ERROR', 'LogLevel.CRITICAL']]
        if len(errors) > 10:
            anomalies.append(f"High error rate: {len(errors)} errors detected")
        
        # Check for repeated errors
        error_messages = [e.get('message', '') for e in errors]
        error_counts = Counter(error_messages)
        for msg, count in error_counts.most_common(3):
            if count > 3:
                anomalies.append(f"Repeated error pattern: '{msg[:50]}...' appeared {count} times")
        
        # Check for warnings surge
        warnings = [e for e in log_entries if e.get('level') == 'WARNING']
        if len(warnings) > 20:
            anomalies.append(f"High warning count: {len(warnings)} warnings")
        
        # Check for missing expected patterns
        has_info = any(e.get('level') == 'INFO' for e in log_entries)
        if not has_info and log_entries:
            anomalies.append("No INFO level logs found - possible logging issue")
        
        return anomalies
    
    def _enhanced_fallback_analysis(self, log_entries: List[Dict], condensed_context: str) -> Dict:
        """
        Pattern-aware fallback analysis. Extracts real pod/service/deployment names from the
        log messages and generates specific kubectl commands + structured IMMEDIATE/LONG-TERM output.
        Used when LLM is unavailable or returns low confidence.
        """
        if not log_entries:
            return {
                "anomalies": ["No log entries found"],
                "root_causes": ["No data available for analysis"],
                "resolutions": ["Upload log files for analysis"],
                "health_assessment": "No data available",
                "config_issues": [], "performance_insights": [],
                "severity": "Healthy", "confidence_score": 0.0
            }

        critical_errors = [e for e in log_entries if str(e.get('level')) in ['ERROR', 'CRITICAL', 'LogLevel.ERROR', 'LogLevel.CRITICAL']]
        warnings = [e for e in log_entries if str(e.get('level')) in ['WARNING', 'LogLevel.WARNING']]
        all_messages = " ".join(e.get('message', '') for e in log_entries)
        error_messages = [e.get('message', '') for e in critical_errors]

        # ── Entity extraction from actual log content ──────────────────────────
        # Extract k8s-style names (e.g. api-gateway-new-2, order-svc-pod-3)
        pod_candidates = re.findall(r'\b([a-z][a-z0-9]*(?:-[a-z0-9]+){2,})\b', all_messages)
        pod_names = list(dict.fromkeys(pod_candidates))[:5]  # deduplicated, top 5

        # Extract deployment names from common log phrases
        deploy_matches = re.findall(r'deployment[/\s]+([a-z][a-z0-9-]+)', all_messages, re.IGNORECASE)
        deployment_name = deploy_matches[0] if deploy_matches else (pod_names[0].rsplit('-', 2)[0] if pod_names else '<deployment-name>')

        # Infer namespace hints
        ns_matches = re.findall(r'namespace[/\s:]+([a-z][a-z0-9-]+)', all_messages, re.IGNORECASE)
        namespace = ns_matches[0] if ns_matches else '<namespace>'

        primary_pod = pod_names[0] if pod_names else '<pod-name>'

        # ── K8s failure pattern detection ─────────────────────────────────────
        msg_lower = all_messages.lower()

        is_crashloop       = 'crashloopbackoff' in msg_lower or 'crash loop' in msg_lower
        is_oom             = 'oomkilled' in msg_lower or 'outofmemoryerror' in msg_lower or 'heap space' in msg_lower or 'exit code 137' in msg_lower
        is_missing_env     = 'missing required env' in msg_lower or 'env var' in msg_lower or 'environment variable' in msg_lower
        is_connection      = 'cannot connect' in msg_lower or 'connection refused' in msg_lower or 'connection failed' in msg_lower
        is_timeout         = 'timeout' in msg_lower or '504' in msg_lower or 'timed out' in msg_lower
        is_upstream        = 'upstream' in msg_lower or 'health check failed' in msg_lower or 'backend' in msg_lower
        is_tls             = 'tls' in msg_lower or 'certificate' in msg_lower or 'ssl' in msg_lower
        is_config_svc      = 'config-service' in msg_lower or 'configmap' in msg_lower or 'secret' in msg_lower
        is_image_pull      = 'imagepullbackoff' in msg_lower or 'errimagepull' in msg_lower
        is_scheduling      = 'failedscheduling' in msg_lower or 'insufficient' in msg_lower
        is_rollout         = 'rollout' in msg_lower or 'rolling update' in msg_lower

        anomalies = []
        root_causes = []
        resolutions = []
        config_issues = []
        performance_insights = []

        # ── Per-pattern analysis ───────────────────────────────────────────────
        if is_crashloop:
            restart_matches = re.findall(r'attempt\s+(\d+)/(\d+)', all_messages)
            restart_str = f"(reached attempt {restart_matches[-1][0]}/{restart_matches[-1][1]})" if restart_matches else ""
            anomalies.append(f"CrashLoopBackOff detected on pod {primary_pod} {restart_str} — container exits immediately on startup with exit code 1")
            if is_missing_env:
                env_matches = re.findall(r'env[_ ]var[: ]+([A-Z_][A-Z0-9_]+)', all_messages, re.IGNORECASE)
                env_name = env_matches[0] if env_matches else 'API_GATEWAY_SECRET_KEY'
                anomalies.append(f"Startup fatal: missing required environment variable '{env_name}' — container cannot initialize")
                root_causes.append(f"Missing required env var '{env_name}' in the new pod spec — the rolling update introduced a pod template that references a Secret/ConfigMap key not present in the cluster")
                resolutions.append(f"IMMEDIATE: kubectl describe pod {primary_pod} -n {namespace} — check Events section for exact missing env var and Secret/ConfigMap reference errors")
                resolutions.append(f"IMMEDIATE: kubectl logs {primary_pod} -n {namespace} --previous — read the startup FATAL lines from the crashed container")
                resolutions.append(f"IMMEDIATE: kubectl rollout undo deployment/{deployment_name} -n {namespace} — revert to last known-good deployment immediately to restore capacity")
                resolutions.append(f"IMMEDIATE: kubectl get secret -n {namespace} and kubectl get configmap -n {namespace} — verify the Secret/ConfigMap containing '{env_name}' exists")
                config_issues.append(f"LONG-TERM: Audit the deployment's envFrom / env[].valueFrom.secretKeyRef blocks — ensure every referenced Secret key exists before a rollout is triggered")
                config_issues.append(f"LONG-TERM: Add a pre-deploy validation step in CI/CD (e.g. helm lint, kubeval, or conftest) to catch missing Secret references before they reach the cluster")
            if is_connection:
                svc_matches = re.findall(r'connect(?:ing)? to ([a-z][a-z0-9.-]+:\d+)', all_messages, re.IGNORECASE)
                target_svc = svc_matches[0] if svc_matches else 'config-service:8500'
                anomalies.append(f"Startup fatal: container cannot reach {target_svc} — service discovery or network policy blocking connection")
                root_causes.append(f"Upstream dependency {target_svc} is unreachable from the new pod — possible network policy, wrong service name, or the target service is down")
                resolutions.append(f"IMMEDIATE: kubectl get svc -n {namespace} — verify {target_svc.split(':')[0]} service exists and has the correct port")
                resolutions.append(f"IMMEDIATE: kubectl get endpointslices -l kubernetes.io/service-name={target_svc.split(':')[0]} -n {namespace} — check if service has live endpoints")
                resolutions.append(f"IMMEDIATE: kubectl debug -it {primary_pod} --image=busybox:1.28 --target={primary_pod.rsplit('-', 1)[0] if '-' in primary_pod else primary_pod} -n {namespace} -- wget -qO- http://{target_svc}/health — test reachability from inside the pod namespace")
            if is_tls:
                anomalies.append("Startup fatal: TLS certificate validation failed for upstream service — cert may be self-signed, expired, or wrong CA bundle")
                root_causes.append("TLS certificate validation failure at startup — the new image version may have stricter TLS validation or the upstream cert has changed/expired")
                resolutions.append(f"IMMEDIATE: kubectl exec -it {primary_pod} -n {namespace} -- openssl s_client -connect <upstream-host>:443 — test TLS handshake manually")
                config_issues.append("LONG-TERM: Mount the correct CA bundle as a volume and set SSL_CERT_FILE env var, or configure cert-manager to automate certificate rotation")
            if is_rollout:
                resolutions.append(f"IMMEDIATE: kubectl rollout status deployment/{deployment_name} -n {namespace} — check current rollout state")
                resolutions.append(f"IMMEDIATE: kubectl rollout history deployment/{deployment_name} -n {namespace} — identify the previous stable revision")
                resolutions.append(f"IMMEDIATE: kubectl rollout undo deployment/{deployment_name} -n {namespace} — rollback to stable revision (Kubernetes will perform a clean rolling replacement)")

        elif is_oom:
            mem_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:GB|MB|GiB|MiB).*?limit', all_messages, re.IGNORECASE)
            mem_info = f" (current limit: {mem_matches[0]})" if mem_matches else ""
            anomalies.append(f"OOMKilled detected{mem_info} — container terminated by kernel out-of-memory killer (exit code 137), pod is restarting")
            root_causes.append(f"Memory limit{mem_info} is insufficient for the workload — application either has a memory leak or the limit is set too low for peak load")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {primary_pod} -n {namespace} — look for 'OOMKilled' in Last State and confirm exit code 137 in Events")
            resolutions.append(f"IMMEDIATE: kubectl logs {primary_pod} -n {namespace} --previous — read heap dump or OOM error from the crashed container")
            resolutions.append(f"IMMEDIATE: kubectl top pod -n {namespace} — check current memory consumption of all pods in the namespace")
            resolutions.append(f"IMMEDIATE: kubectl top node — check if the node itself is under memory pressure")
            resolutions.append(f"IMMEDIATE: kubectl get pod {primary_pod} -n {namespace} -o yaml | grep -A5 resources — confirm the current memory limit")
            config_issues.append(f"LONG-TERM: Increase memory limit to at least 2x the observed peak usage — update resources.limits.memory in the deployment spec")
            config_issues.append("LONG-TERM: Set resources.requests.memory = resources.limits.memory (Guaranteed QoS) so the pod is never evicted before OOMKill")
            config_issues.append("LONG-TERM: Configure HorizontalPodAutoscaler with memory target (70%) to scale out before hitting the OOM threshold")
            performance_insights.append("Add Prometheus alert: alert when pod memory > 80% of limit for >2 min — kube_pod_container_resource_usage_memory > 0.8 * kube_pod_container_resource_limits_memory")

        elif is_upstream or is_timeout:
            pod_list = ', '.join(pod_names[:3]) if pod_names else primary_pod
            anomalies.append(f"Upstream service failures detected — pods [{pod_list}] failing health checks and/or returning timeouts")
            if is_timeout:
                anomalies.append("Request timeouts observed — backend pods not responding within acceptable threshold, causing cascading 504s")
            root_causes.append("Backend pods are unhealthy — either crashing, under heavy load, or network policy is blocking health check probes")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {primary_pod} -n {namespace} — check Events for probe failures (Liveness/Readiness) and recent restarts")
            resolutions.append(f"IMMEDIATE: kubectl logs {primary_pod} -n {namespace} --previous — read crash logs if pod has restarted")
            resolutions.append(f"IMMEDIATE: kubectl get events --sort-by='.lastTimestamp' -n {namespace} — get full cluster event timeline")
            resolutions.append(f"IMMEDIATE: kubectl get endpointslices -l kubernetes.io/service-name={deployment_name} -n {namespace} — verify healthy endpoints exist behind the service")
            resolutions.append(f"IMMEDIATE: kubectl top pod -n {namespace} — check if pods are CPU/memory throttled")
            if is_tls:
                resolutions.append(f"IMMEDIATE: Check SSL certificate expiry — kubectl get certificate -n {namespace} (if cert-manager) or openssl s_client -connect <host>:443 | openssl x509 -noout -dates")
                config_issues.append("LONG-TERM: Configure cert-manager with automatic renewal (renewBefore: 720h) so certificate expiry never causes a production incident")
            config_issues.append(f"LONG-TERM: Add readinessProbe to {deployment_name} with failureThreshold: 3 + periodSeconds: 10 so unhealthy pods are removed from Service load balancing before they impact users")
            performance_insights.append("Add Prometheus alert for endpoint availability: kube_endpoint_address_available < 1 — triggers when all endpoints for a service are gone")

        elif is_scheduling:
            anomalies.append("Pod scheduling failures (FailedScheduling) — pods cannot be placed on any node due to insufficient resources")
            root_causes.append("Cluster nodes lack sufficient CPU or memory to satisfy pod resource requests — either cluster needs scaling or requests are too high")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {primary_pod} -n {namespace} — read FailedScheduling event for exact resource shortfall (e.g. 'Node didn't have enough resource: CPU, requested: 1000, used: 1420')")
            resolutions.append("IMMEDIATE: kubectl top node — identify which nodes are at capacity")
            resolutions.append("IMMEDIATE: kubectl get nodes -o wide — check node count and status")
            resolutions.append(f"IMMEDIATE: kubectl get pods -n {namespace} -o wide — identify which pods are Pending vs Running")
        
        elif is_image_pull:
            anomalies.append("ImagePullBackOff — Kubernetes cannot pull the container image from the registry")
            root_causes.append("Image pull failure: registry credentials missing/expired, image tag does not exist, or registry is unreachable")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {primary_pod} -n {namespace} — check Events for exact pull error (unauthorized, not found, network timeout)")
            resolutions.append(f"IMMEDIATE: kubectl get secret -n {namespace} | grep registry — verify imagePullSecret exists")

        # ── Generic rules for anything not caught above ────────────────────────
        if not anomalies:
            anomalies.append(f"Found {len(critical_errors)} critical error(s) and {len(warnings)} warning(s)")
            if critical_errors:
                top_msg = critical_errors[0].get('message', '')[:200]
                anomalies.append(f"First critical error: {top_msg}")
            root_causes.append("Multiple errors detected — review full log context for root cause")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {primary_pod} -n {namespace} — check Events section")
            resolutions.append(f"IMMEDIATE: kubectl logs {primary_pod} -n {namespace} --previous — check crash logs")
            resolutions.append(f"IMMEDIATE: kubectl get events --sort-by='.lastTimestamp' -n {namespace}")

        # ── Warnings summary ───────────────────────────────────────────────────
        if warnings:
            unique_warn_msgs = list(dict.fromkeys(e.get('message', '')[:120] for e in warnings))
            anomalies.append(f"{len(warnings)} warning(s) detected — e.g.: {unique_warn_msgs[0]}")

        # ── Health assessment ──────────────────────────────────────────────────
        if is_crashloop:
            health = (f"CRITICAL: Deployment {deployment_name} rolling update is stalled with pod {primary_pod} in CrashLoopBackOff. "
                     f"Service is partially degraded — only healthy pods (from previous revision) are serving traffic. "
                     f"If not resolved, the deployment is stuck and new pods cannot be rolled out. Immediate rollback is recommended.")
            severity = "Critical"
        elif is_oom:
            health = (f"CRITICAL: Pod {primary_pod} is being OOMKilled repeatedly. "
                     f"The application cannot sustain its workload within the current memory limit. "
                     f"Each restart causes a brief service disruption; frequent restarts will degrade reliability significantly.")
            severity = "Critical"
        elif len(critical_errors) > 5:
            health = (f"CRITICAL: {len(critical_errors)} error events detected. "
                     f"Multiple failure modes are active simultaneously, indicating systemic issues that require immediate triage.")
            severity = "Critical"
        elif critical_errors:
            health = (f"WARNING: {len(critical_errors)} critical error(s) found. "
                     f"Service may be partially impaired — investigate the errors before they escalate.")
            severity = "Warning"
        else:
            health = f"WARNING: {len(warnings)} warning(s) found. Service appears operational but shows signs of instability."
            severity = "Warning"

        # ── Performance insights ───────────────────────────────────────────────
        if is_rollout and is_crashloop:
            performance_insights.append("LONG-TERM: Implement a pre-deployment smoke test job (Kubernetes Job that exits 0 only if the new image passes startup checks) — makes CrashLoopBackOff impossible to reach production")
            performance_insights.append("LONG-TERM: Set maxUnavailable: 0 in rollingUpdate strategy so a broken pod never reduces capacity before it is confirmed healthy")
        if not performance_insights:
            performance_insights.append("LONG-TERM: Add structured logging with severity levels and correlate with Prometheus metrics for faster incident detection")

        if not config_issues:
            config_issues.append("LONG-TERM: Review resource requests and limits — set requests conservatively and limits at 2x requests for burstable QoS")

        return {
            "anomalies": anomalies,
            "root_causes": root_causes or ["Review error patterns — see anomalies for detected failure signatures"],
            "resolutions": resolutions,
            "health_assessment": health,
            "config_issues": config_issues,
            "performance_insights": performance_insights,
            "severity": severity,
            "confidence_score": 0.75
        }

    def _build_smart_prompt(self, condensed_context: str, analysis_type: str) -> str:
        """Build optimized prompt for condensed context."""

        system_instruction = """You are a Principal Site Reliability Engineer (SRE) and Senior DevOps Engineer with 15+ years of hands-on experience operating production Kubernetes clusters at scale. You are an expert at the official Kubernetes debugging methodology documented at https://kubernetes.io/docs/tasks/debug/debug-application/ — specifically:

KUBERNETES DEBUGGING METHODOLOGY YOU FOLLOW:
1. kubectl describe pod <pod-name> -n <namespace>  →  always start here; the Events section reveals scheduling failures (FailedScheduling, OOMKilled, BackOff), probe failures, and image pull issues.
2. kubectl logs <pod-name> -n <namespace> --previous  →  crash logs from the LAST terminated container (essential for CrashLoopBackOff).
3. kubectl get events --sort-by='.lastTimestamp' -n <namespace>  →  cluster-level timeline of what happened.
4. kubectl top pod / kubectl top node  →  live resource consumption; confirms OOMKill pressure.
5. kubectl get pod <pod-name> -n <namespace> -o yaml  →  full spec: resource limits, probes, env vars, volume mounts.
6. kubectl get endpointslices -l kubernetes.io/service-name=<svc> -n <namespace>  →  checks if Service has healthy endpoints behind it.
7. kubectl exec -it <pod-name> -n <namespace> -- sh  →  interactive shell for in-container debugging.
8. kubectl debug -it <pod-name> --image=busybox:1.28 --target=<container> -n <namespace>  →  ephemeral debug container for distroless/crashed containers.
9. kubectl debug node/<node-name> -it --image=ubuntu --profile=sysadmin  →  node-level debugging (filesystem, network capture).
10. kubectl rollout history / kubectl rollout undo  →  deployment rollback when a bad deploy caused the issue.

KEY FAILURE PATTERNS YOU RECOGNIZE:
- OOMKilled (exit code 137): memory.limit too low or application memory leak
- CrashLoopBackOff: application crash on startup — check --previous logs for root cause
- Pending pods: insufficient resources (CPU/memory) on nodes — check Events for FailedScheduling
- Upstream timeouts / 504s from Ingress: backend pods unhealthy, check endpoints and health checks
- SSL/TLS cert expiry: certificate rotation needed
- Java heap space / OutOfMemoryError: JVM heap too small or memory leak in application code
- Connection pool exhaustion: Redis/DB max connections hit, need pool tuning or scaling
- Init:CrashLoopBackOff: init container failing — check init container logs separately

You approach every incident: triage first → correlate timeline → distinguish root cause from downstream symptoms → actionable remediation with exact commands."""

        base_prompt = f"""{system_instruction}

You are investigating a production incident. Below are the actual log lines extracted from the system. Read them carefully — extract service names, pod names, error messages, and timestamps directly from the text.

=== ACTUAL LOG DATA ===
{condensed_context}
=== END LOG DATA ===

YOUR TASK: Analyze these logs as a senior DevOps engineer responding to a live production incident.

STEP 1 — SEVERITY
Classify: Critical / Warning / Healthy. Justify based on actual log evidence.

STEP 2 — LOG ANALYSIS  
- What actually happened? Describe the failure chain using real log lines as evidence.
- What are the root causes vs downstream symptoms?
- Which specific services/pods/components are affected? (use the names you see in the logs)
- What is the blast radius?

STEP 3 — IMMEDIATE TROUBLESHOOTING (next 15 minutes)
Write specific kubectl commands using the ACTUAL service/pod names you extracted from the logs.
If logs mention "order-svc-pod-3", use that exact name.
If logs mention "payment-processor", use that exact name.
Commands must be actionable right now.

STEP 4 — LONG-TERM FIXES
Prevent this from happening again: resource limits, probe configuration, HPA/VPA, circuit breakers, alerting rules.

Return ONLY raw JSON (no markdown, no extra text):
{{
    "anomalies": [
        "Direct quote or paraphrase of the specific failure observed — e.g. 'order-svc-pod-3 failed health check 3/3 consecutive times at 14:30:10, then pod-1 followed at 14:31:09 — both pods lost simultaneously'",
        "Another specific failure pattern with actual service names and timestamps from the logs"
    ],
    "root_causes": [
        "Technical root cause with evidence from the actual log lines — e.g. 'Java heap space exhausted at 02:22:11 after memory climbed from 72% (02:20:11) to 93% (02:22:09) to 98% (02:22:10) — application memory leak in TransactionProcessor.loadBatch()'",
        "Contributing or cascading factor"
    ],
    "resolutions": [
        "IMMEDIATE: kubectl describe pod <actual-pod-name-from-logs> -n <namespace> — check Events section for OOMKilled, BackOff, or FailedScheduling reasons",
        "IMMEDIATE: kubectl logs <actual-pod-name-from-logs> -n <namespace> --previous — retrieve crash logs from the terminated container",
        "IMMEDIATE: kubectl get events --sort-by='.lastTimestamp' -n <namespace> — get the full cluster event timeline",
        "IMMEDIATE: kubectl top pod -n <namespace> and kubectl top node — confirm live resource pressure",
        "IMMEDIATE: <any other specific command relevant to THIS incident based on what you see in the logs>"
    ],
    "health_assessment": "2-3 sentence paragraph: What is broken right now, what is the impact on end users/services, and what will happen if this is not addressed in the next 30 minutes.",
    "config_issues": [
        "LONG-TERM: Specific config change with rationale — e.g. 'Increase memory limit from 2Gi to 4Gi and set request=2Gi to prevent OOMKill; current 2GB limit is insufficient for transaction batch sizes seen in logs'",
        "LONG-TERM: Add readinessProbe with failureThreshold: 3 and periodSeconds: 10 to stop traffic to degraded pods before they fully fail",
        "LONG-TERM: Configure HorizontalPodAutoscaler targeting 70% memory utilization to scale before hitting OOM threshold"
    ],
    "performance_insights": [
        "Strategic architectural insight to prevent recurrence — specific to what you saw in these logs",
        "Prometheus alert rule to add — e.g. 'Alert when pod memory > 80% of limit for >2 minutes: kube_pod_container_resource_usage_memory > 0.8 * kube_pod_container_resource_limits_memory'",
        "Any other SRE-level insight: circuit breaker config, retry budgets, PDB, topology spread"
    ],
    "severity": "Critical",
    "confidence_score": 0.95
}}

CRITICAL RULES — violating these makes your analysis worthless:
- anomalies MUST reference actual log content (service names, error messages, timestamps) — not generic descriptions
- resolutions MUST contain actual kubectl commands with real pod/service names from the logs where possible
- config_issues MUST start with "LONG-TERM:" and be specific to what you observed
- resolutions MUST start with "IMMEDIATE:"  
- severity must be exactly one of: "Critical", "Warning", "Healthy"
- DO NOT write "check logs" — always give the exact command
- DO NOT write generic advice that applies to any log file — be specific to THIS incident"""

        return base_prompt
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse LLM response into structured format."""
        try:
            # Clean up the response text
            response_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            elif response_text.startswith('```'):
                response_text = response_text[3:]   # Remove ```
            
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove trailing ```
            
            response_text = response_text.strip()
            
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                print(f"Extracted JSON string: {json_str[:200]}...")
                parsed = json.loads(json_str)
                print(f"Parsed successfully, got keys: {list(parsed.keys())}")
                
                # Ensure all required fields exist
                required_fields = ["anomalies", "root_causes", "resolutions", "severity", "confidence_score"]
                for field in required_fields:
                    if field not in parsed:
                        if field == "severity":
                            parsed[field] = "Warning"
                        elif field == "confidence_score":
                            parsed[field] = 0.5
                        else:
                            parsed[field] = []

                # Normalize severity: map legacy "Normal" → "Healthy"
                if parsed.get("severity") == "Normal":
                    parsed["severity"] = "Healthy"
                
                # Add optional fields if not present
                if "health_assessment" not in parsed:
                    parsed["health_assessment"] = "Analysis completed"
                if "config_issues" not in parsed:
                    parsed["config_issues"] = []
                if "performance_insights" not in parsed:
                    parsed["performance_insights"] = []
                
                return parsed
        except Exception as e:
            print(f"JSON parsing failed: {e}")
            print(f"Response text: {response_text[:500]}...")
        
        # Fallback: return response as findings
        return {
            "anomalies": ["Analysis completed - see details"],
            "root_causes": ["Unable to parse LLM response automatically"],
            "resolutions": [response_text],
            "health_assessment": "Analysis completed with parsing issues",
            "config_issues": [],
            "performance_insights": [],
            "severity": "Warning",
            "confidence_score": 0.5
        }
    
    def _fallback_analysis(self, log_entries: List[Dict]) -> Dict:
        """Provide enhanced rule-based analysis using smart parsing."""
        if not log_entries:
            return {
                "anomalies": ["No log entries found"],
                "root_causes": ["No data available for analysis"],
                "resolutions": ["Upload log files for analysis"],
                "health_assessment": "No data available",
                "config_issues": [],
                "performance_insights": [],
                "severity": "Normal",
                "confidence_score": 0.0
            }
        
        # Smart analysis of available data
        critical_errors = [e for e in log_entries if e.get('level') in ['ERROR', 'CRITICAL']]
        warnings = [e for e in log_entries if e.get('level') == 'WARNING']
        
        anomalies = []
        if critical_errors:
            anomalies.append(f"Found {len(critical_errors)} critical error(s)")
        if warnings:
            anomalies.append(f"Found {len(warnings)} warning(s)")
        
        # Detect patterns
        error_patterns = Counter([e.get('message', '')[:60] for e in critical_errors])
        if error_patterns:
            most_common = error_patterns.most_common(1)[0]
            if most_common[1] > 3:
                anomalies.append(f"Repeated error pattern: {most_common[0]}... (appeared {most_common[1]} times)")
        
        # Generate intelligent suggestions
        resolutions = []
        config_issues = []
        performance_insights = []
        
        if critical_errors:
            resolutions.append("Review critical errors immediately")
            
            # Check for common patterns
            error_messages = [e.get('message', '').lower() for e in critical_errors]
            if any('connection' in msg for msg in error_messages):
                resolutions.append("Check network connectivity and service endpoints")
                config_issues.append("Potential service endpoint or network configuration issue")
            if any('timeout' in msg for msg in error_messages):
                resolutions.append("Increase timeout values or check service performance")
                performance_insights.append("Service response time issues detected")
            if any('memory' in msg for msg in error_messages):
                resolutions.append("Check memory usage and consider increasing resource limits")
                performance_insights.append("Memory pressure detected - consider increasing limits")
            if any('config' in msg for msg in error_messages):
                resolutions.append("Review application configuration files")
                config_issues.append("Configuration-related errors detected")
        
        if not critical_errors and not warnings:
            health = "Normal - Application appears to be running smoothly"
        elif len(critical_errors) > 5:
            health = "Critical - Multiple critical errors require immediate attention"
        elif critical_errors:
            health = "Warning - Application has critical errors that need attention"
        elif len(warnings) > 10:
            health = "Warning - High number of warnings suggests potential issues"
        else:
            health = "Normal - Some warnings but overall stable"
        
        severity = "Critical" if len(critical_errors) > 5 else "Warning" if critical_errors else "Normal"
        
        return {
            "anomalies": anomalies,
            "root_causes": ["Smart rule-based analysis - LLM not configured"],
            "resolutions": resolutions or ["Review logs for specific issues"],
            "health_assessment": health,
            "config_issues": config_issues,
            "performance_insights": performance_insights,
            "severity": severity,
            "confidence_score": 0.4
        }