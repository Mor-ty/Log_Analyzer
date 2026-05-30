import json
from typing import List, Dict, Optional, Set
from openai import AzureOpenAI
from collections import Counter
from datetime import datetime
import re
from app.core.config import settings


class LLMLogAnalyzer:
    """Use LLM to analyze logs with smart parsing and condensation for efficiency."""
    
    def __init__(self):
        self.client = None
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        if settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY:
            try:
                self.client = AzureOpenAI(
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                )
                print(f"Azure OpenAI client initialized — deployment: {self.deployment}, api_version: {settings.AZURE_OPENAI_API_VERSION}")
            except Exception as e:
                print(f"Failed to initialize Azure OpenAI client: {e}")
    
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
                messages = self._build_smart_prompt(condensed_context, analysis_type)
                print(f"Attempting Azure OpenAI analysis (deployment={self.deployment}), messages built...")
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                    max_completion_tokens=16000,
                    reasoning_effort="medium",
                )
                response_text = response.choices[0].message.content or ""
                print(f"Azure OpenAI response received ({len(response_text)} chars), parsing...")
                result = self._parse_response(response_text)
                confidence = result.get("confidence_score", 0)
                print(f"Parsed result confidence: {confidence}")
                # Accept LLM result whenever it returns a valid structured response
                # (confidence >= 0.4 means the LLM produced something meaningful)
                if confidence >= 0.4:
                    print(f"Using Azure OpenAI analysis (confidence={confidence})")
                    return result
                else:
                    print(f"Gemini returned very low confidence ({confidence}), using pattern-aware fallback")
                    return self._enhanced_fallback_analysis(log_entries, condensed_context)
            except Exception as e:
                print(f"Azure OpenAI analysis failed — {type(e).__name__}: {e}")
                print("Falling back to pattern-aware rule-based analysis")
                return self._enhanced_fallback_analysis(log_entries, condensed_context)
        else:
            print("LLM not configured, using enhanced rule-based analysis")
            return self._enhanced_fallback_analysis(log_entries, condensed_context)
    
    def _prepare_condensed_context(self, log_entries: List[Dict]) -> str:
        """
        Token-efficient context: group all log levels by normalised pattern with
        count + time range so the LLM gets signal-dense input without redundant repetition.
        """
        critical_errors = [e for e in log_entries if str(e.get('level')) in ['ERROR', 'CRITICAL', 'LogLevel.ERROR', 'LogLevel.CRITICAL']]
        warnings = [e for e in log_entries if str(e.get('level')) in ['WARNING', 'LogLevel.WARNING']]
        info_entries = [e for e in log_entries if str(e.get('level')) in ['INFO', 'LogLevel.INFO']]
        debug_entries = [e for e in log_entries if str(e.get('level')) in ['DEBUG', 'LogLevel.DEBUG']]

        context_parts = []

        # --- Summary header ---
        context_parts.append("=== LOG SUMMARY ===")
        context_parts.append(
            f"Entries: {len(log_entries)} total | "
            f"ERROR/CRITICAL: {len(critical_errors)} | WARNING: {len(warnings)} | "
            f"INFO: {len(info_entries)} | DEBUG: {len(debug_entries)}"
        )
        if log_entries:
            context_parts.append(
                f"Time range: {log_entries[0].get('timestamp', 'N/A')} → {log_entries[-1].get('timestamp', 'N/A')}"
            )

        # --- Unique error patterns grouped by normalized message ---
        error_groups: Dict[str, list] = {}
        for e in critical_errors:
            key = self._normalize_message(e.get('message', ''))[:100]
            if key not in error_groups:
                error_groups[key] = []
            error_groups[key].append(e)

        sorted_errors = sorted(error_groups.items(), key=lambda x: len(x[1]), reverse=True)
        if sorted_errors:
            context_parts.append(
                f"\n=== UNIQUE ERROR PATTERNS ({len(sorted_errors)} distinct, {len(critical_errors)} total) ==="
            )
            for _, group in sorted_errors[:15]:
                count = len(group)
                first = group[0]
                first_ts = first.get('timestamp', '')
                last_ts = group[-1].get('timestamp', '') if count > 1 else ''
                svc = first.get('service', first.get('source', ''))
                msg = first.get('message', '')[:220]
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

        # --- INFO patterns grouped by pattern (not just a sample) ---
        info_groups: Dict[str, list] = {}
        for e in info_entries:
            key = self._normalize_message(e.get('message', ''))[:100]
            if key not in info_groups:
                info_groups[key] = []
            info_groups[key].append(e)

        sorted_info = sorted(info_groups.items(), key=lambda x: len(x[1]), reverse=True)
        if sorted_info:
            context_parts.append(
                f"\n=== INFO PATTERNS ({len(sorted_info)} distinct, {len(info_entries)} total) ==="
            )
            for _, group in sorted_info[:12]:
                count = len(group)
                first = group[0]
                ts = first.get('timestamp', '')
                msg = first.get('message', '')[:200]
                context_parts.append(f"  [{count}x] {ts}: {msg}")

        # --- DEBUG sample (top 3 unique patterns if present) ---
        if debug_entries:
            debug_groups: Dict[str, list] = {}
            for e in debug_entries:
                key = self._normalize_message(e.get('message', ''))[:100]
                if key not in debug_groups:
                    debug_groups[key] = []
                debug_groups[key].append(e)
            sorted_debug = sorted(debug_groups.items(), key=lambda x: len(x[1]), reverse=True)
            context_parts.append(
                f"\n=== DEBUG SAMPLE ({len(debug_entries)} total, {len(sorted_debug)} distinct) ==="
            )
            for _, group in sorted_debug[:3]:
                count = len(group)
                first = group[0]
                msg = first.get('message', '')[:120]
                context_parts.append(f"  [{count}x] {msg}")

        # --- Stack trace signatures (deduplicated by first 80 chars) ---
        stack_traces = self._extract_stack_traces(log_entries)
        if stack_traces:
            unique_traces = list({t[:80]: t for t in stack_traces}.values())
            context_parts.append(f"\n=== STACK TRACES ({len(unique_traces)} unique) ===")
            for trace in unique_traces[:3]:
                context_parts.append(f"  {trace[:350]}")

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

    def _detect_log_source(self, log_entries: List[Dict]) -> Dict[str, bool]:
        """Detect what types of logs are present: K8s, kubelet, Apache, Nginx, Java, Python."""
        all_text = " ".join(
            e.get('message', '') + " " + str(e.get('source', '')) + " " + str(e.get('service', ''))
            for e in log_entries
        )
        msg_lower = all_text.lower()

        has_k8s_paths  = bool(re.search(r'/var/log/pods/|namespace[/\s:]+\w', all_text))
        has_k8s_events = bool(re.search(
            r'crashloopbackoff|oomkilled|imagepullbackoff|failedscheduling|kubeconfig|k8s\.io',
            msg_lower
        ))
        has_kubelet = bool(re.search(r'resolving symlinks|kubelet|/var/log/pods/', all_text))
        has_apache  = bool(re.search(r'ah\d{5}|apache|httpd|mod_|mpm_prefork|mpm_event|servername', msg_lower))
        has_nginx   = bool(re.search(r'\bnginx\b|worker_process|accept\(\) failed|proxy_pass', msg_lower))
        has_java    = bool(re.search(
            r'at\s+[\w$.]+\([\w$.]+\.java:\d+\)|java\.lang\.|heap space|outofmemoryerror', msg_lower
        ))
        has_python  = bool(re.search(
            r'traceback \(most recent call|file ".+\.py", line|importerror|modulenotfounderror', msg_lower
        ))
        has_k8s = has_k8s_paths or has_k8s_events or has_kubelet

        return {
            'k8s': has_k8s,
            'k8s_paths': has_k8s_paths,
            'kubelet': has_kubelet,
            'apache': has_apache,
            'nginx': has_nginx,
            'java': has_java,
            'python': has_python,
        }

    def _extract_k8s_entities_from_paths(self, log_entries: List[Dict]) -> Dict[str, Set[str]]:
        """
        Extract namespace, pod name, and container name from /var/log/pods/ paths in log messages.
        Path format: /var/log/pods/NAMESPACE_PODNAME_UUID/CONTAINER/N.log
        """
        namespaces: Set[str] = set()
        pods: Set[str] = set()
        containers: Set[str] = set()

        all_text = " ".join(e.get('message', '') for e in log_entries)
        path_pattern = re.compile(
            r'/var/log/pods/'
            r'([a-z0-9][a-z0-9-]*)'                                                    # namespace
            r'_([a-z0-9][a-z0-9.-]*[a-z0-9])'                                         # pod name
            r'_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'       # UUID
            r'/([a-z0-9][a-z0-9-]*)'                                                   # container
            r'/',
            re.IGNORECASE
        )
        for m in path_pattern.finditer(all_text):
            namespaces.add(m.group(1).lower())
            pods.add(m.group(2).lower())
            containers.add(m.group(4).lower())

        return {'namespaces': namespaces, 'pods': pods, 'containers': containers}

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
        """Rule-based fallback used only when the LLM is unavailable or returns low confidence."""
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
        warnings        = [e for e in log_entries if str(e.get('level')) in ['WARNING', 'LogLevel.WARNING']]
        all_messages    = " ".join(e.get('message', '') for e in log_entries)
        msg_lower       = all_messages.lower()

        # Extract real pod/namespace names from log text
        pod_candidates  = re.findall(r'\b([a-z][a-z0-9]*(?:-[a-z0-9]+){2,})\b', all_messages)
        pod_names       = list(dict.fromkeys(pod_candidates))[:5]
        ns_matches      = re.findall(r'namespace[/\s:]+([a-z][a-z0-9-]+)', all_messages, re.IGNORECASE)
        # Also parse /var/log/pods/NAMESPACE_PODNAME_UUID/CONTAINER/ paths
        path_ns = re.findall(r'/var/log/pods/([a-z0-9][a-z0-9-]*)_[a-z0-9]', all_messages, re.IGNORECASE)
        path_pods = re.findall(r'/var/log/pods/[a-z0-9][a-z0-9-]*_([a-z0-9][a-z0-9.-]*[a-z0-9])_[0-9a-f-]{36}', all_messages, re.IGNORECASE)

        all_pods = list(dict.fromkeys((path_pods or []) + pod_names))
        all_ns   = list(dict.fromkeys((path_ns or []) + (ns_matches or [])))
        primary_pod = all_pods[0] if all_pods else None
        namespace   = all_ns[0] if all_ns else None
        ns_str  = namespace or "<namespace>"
        pod_str = primary_pod or "<pod-name>"

        deploy_matches  = re.findall(r'deployment[/\s]+([a-z][a-z0-9-]+)', all_messages, re.IGNORECASE)
        deployment_name = deploy_matches[0] if deploy_matches else (
            primary_pod.rsplit('-', 2)[0] if primary_pod and primary_pod.count('-') >= 2 else pod_str
        )

        is_k8s       = bool(re.search(r'/var/log/pods/|crashloopbackoff|oomkilled|imagepullbackoff|failedscheduling', msg_lower))
        is_crashloop = 'crashloopbackoff' in msg_lower
        is_oom       = 'oomkilled' in msg_lower or 'outofmemoryerror' in msg_lower or 'heap space' in msg_lower or 'exit code 137' in msg_lower
        is_image     = 'imagepullbackoff' in msg_lower or 'errimagepull' in msg_lower
        is_schedule  = 'failedscheduling' in msg_lower or 'insufficient' in msg_lower
        is_timeout   = 'timeout' in msg_lower or '504' in msg_lower or 'connection refused' in msg_lower

        anomalies: list = []
        root_causes: list = []
        resolutions: list = []
        config_issues: list = []
        performance_insights: list = []

        if is_crashloop:
            anomalies.append(f"CrashLoopBackOff detected on pod {pod_str} — container crashes on every start")
            root_causes.append("Application exits immediately at startup — check --previous logs for the exact error")
            resolutions.append(f"IMMEDIATE: kubectl logs {pod_str} -n {ns_str} --previous -- read crash output from last run")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {pod_str} -n {ns_str} -- check Events for BackOff reason")
            resolutions.append(f"IMMEDIATE: kubectl rollout undo deployment/{deployment_name} -n {ns_str} -- rollback if caused by a bad deploy")
        elif is_oom:
            anomalies.append(f"OOMKilled on pod {pod_str} (exit 137) — kernel terminated container for exceeding memory limit")
            root_causes.append("Memory limit is too low for the workload or the application has a memory leak")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {pod_str} -n {ns_str} -- confirm OOMKilled in Last State")
            resolutions.append(f"IMMEDIATE: kubectl logs {pod_str} -n {ns_str} --previous -- check heap dump / OOM error in app output")
            resolutions.append(f"IMMEDIATE: kubectl top pod -n {ns_str} -- check live memory usage")
            config_issues.append("LONG-TERM: Increase resources.limits.memory to at least 2x observed peak usage")
        elif is_image:
            anomalies.append(f"ImagePullBackOff on pod {pod_str} — Kubernetes cannot pull the container image")
            root_causes.append("Bad image tag, missing imagePullSecret, or registry unreachable")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {pod_str} -n {ns_str} -- read exact pull error from Events")
            resolutions.append(f"IMMEDIATE: kubectl get secret -n {ns_str} | grep registry -- verify imagePullSecret exists")
        elif is_schedule:
            anomalies.append(f"FailedScheduling — pod {pod_str} cannot be placed on any node")
            root_causes.append("Cluster nodes lack sufficient CPU or memory for the pod's resource requests")
            resolutions.append(f"IMMEDIATE: kubectl describe pod {pod_str} -n {ns_str} -- read resource shortfall from Events")
            resolutions.append("IMMEDIATE: kubectl top node -- identify nodes at capacity")
        elif is_timeout:
            anomalies.append("Connection timeouts or 504 errors detected — backend pods may be unhealthy or overloaded")
            root_causes.append("Upstream service unavailable or responding too slowly")
            if is_k8s:
                resolutions.append(f"IMMEDIATE: kubectl describe pod {pod_str} -n {ns_str} -- check probe failures in Events")
                resolutions.append(f"IMMEDIATE: kubectl top pod -n {ns_str} -- check for CPU/memory throttling")
        elif critical_errors:
            anomalies.append(f"{len(critical_errors)} critical error(s) detected")
            if critical_errors:
                anomalies.append(f"First error: {critical_errors[0].get('message', '')[:200]}")
            root_causes.append("Application errors — review full log context for root cause")
            if is_k8s:
                resolutions.append(f"IMMEDIATE: kubectl describe pod {pod_str} -n {ns_str}")
                resolutions.append(f"IMMEDIATE: kubectl logs {pod_str} -n {ns_str} --previous")
                resolutions.append(f"IMMEDIATE: kubectl get events --sort-by=.lastTimestamp -n {ns_str}")
        else:
            anomalies.append(f"{len(critical_errors)} error(s), {len(warnings)} warning(s) — system may be healthy or partially degraded")
            root_causes.append("No dominant failure pattern detected — review logs manually")
            resolutions.append("IMMEDIATE: Review the log entries above for specific error signatures")

        if warnings:
            anomalies.append(f"{len(warnings)} warning(s) also present — e.g. {warnings[0].get('message','')[:120]}")

        if not config_issues:
            config_issues.append("LONG-TERM: Ensure resource requests and limits are set on all containers to prevent OOMKill and throttling")
        if not performance_insights:
            performance_insights.append("Add Prometheus alerts for pod restart rate and memory utilisation to detect these issues earlier")

        if is_crashloop or is_oom:
            severity = "Critical"
            health   = f"CRITICAL: Pod {pod_str} is in a failure loop. Service capacity is degraded. Immediate action required."
        elif critical_errors:
            severity = "Warning"
            health   = f"WARNING: {len(critical_errors)} error(s) detected. Investigate before they escalate."
        elif warnings:
            severity = "Warning"
            health   = f"WARNING: {len(warnings)} warning(s) present. System appears operational but needs attention."
        else:
            severity = "Healthy"
            health   = "System appears healthy based on available log data."

        return {
            "anomalies": anomalies,
            "root_causes": root_causes,
            "resolutions": resolutions,
            "health_assessment": health,
            "config_issues": config_issues,
            "performance_insights": performance_insights,
            "severity": severity,
            "confidence_score": 0.65
        }

    def _build_smart_prompt(self, condensed_context: str, analysis_type: str) -> List[Dict[str, str]]:
        """Build chat messages for Azure OpenAI: system instruction + user log data."""

        system_instruction = """You are a senior Kubernetes SRE and log analysis expert. Analyse the provided pod/cluster logs and return structured troubleshooting intelligence.

ANALYSIS RULES:
- Read every log level. INFO is often the real signal: repeated startup lines = restarts, path errors = infrastructure issues, config warnings = misconfigurations.
- Extract pod names, namespaces, containers, IPs, and service names directly from the log text. Never invent or guess names.
- Use kubectl commands only when logs contain Kubernetes context (pod paths, namespace refs, K8s events). For non-K8s logs use appropriate system tools.
- Every finding must be tied to specific content from the provided logs — no generic advice.

K8s PATH FORMAT — parse these to get real entity names:
  /var/log/pods/NAMESPACE_PODNAME_UUID/CONTAINER/N.log
  e.g. /var/log/pods/default_mywebapp-release-55b79f8579-fwkvh_5e69fa47-35fe-4ab9-a69e-3686915b6081/webapp/6.log
  → namespace=default | pod=mywebapp-release-55b79f8579-fwkvh | container=webapp

K8s TROUBLESHOOTING (use actual names from the logs, not placeholders):
  kubectl describe pod <POD> -n <NS>                    → Events: OOMKill, BackOff, probe/image failures
  kubectl logs <POD> -n <NS> --previous                 → crash output from last container run
  kubectl get events --sort-by=.lastTimestamp -n <NS>   → full incident timeline
  kubectl top pod -n <NS> / kubectl top node            → live resource pressure
  kubectl rollout undo deployment/<DEPLOY> -n <NS>      → rollback a bad deploy

KNOWN PATTERNS:
  OOMKilled / exit 137          → memory limit or leak; check --previous logs + kubectl top
  CrashLoopBackOff              → app crashes on startup; kubectl logs --previous reveals exact reason
  FailedScheduling / Pending    → node lacks CPU/memory; kubectl describe pod + kubectl top node
  ImagePullBackOff              → bad image tag or missing registry credentials
  Symlink error in /var/log/pods/... → log collector read a rotated file; pod is likely NOT crashing
  Repeated startup INFO lines   → container is cycling; check restart count
  504 / upstream timeout        → backend pods unhealthy; kubectl get endpointslices + kubectl top pod"""

        user_content = f"""=== LOG DATA ===
{condensed_context}
=== END ===

Return ONLY a raw JSON object — no markdown fences, no text outside the JSON:
{{
  "anomalies": [
    "Specific finding with real names and log evidence — e.g. 'Pod mywebapp-release-55b79f8579-fwkvh (ns: default): kubelet emitted INFO symlink error for webapp/6.log — log collector read a file already rotated away; appeared 2x'"
  ],
  "root_causes": [
    "Root cause grounded in log evidence — e.g. 'Log-rotation race: kubelet rotated webapp/6.log while the collector still held a file handle. Pod is running normally; this is a log pipeline lag issue, not a pod failure.'"
  ],
  "resolutions": [
    "IMMEDIATE: kubectl get pod <real-pod-name> -n <real-namespace> — verify pod status and restart count",
    "IMMEDIATE: <next exact command using real names extracted from the logs>"
  ],
  "health_assessment": "2-3 sentences on current system state, user/service impact, and what happens if unaddressed — specific to these logs only.",
  "config_issues": [
    "LONG-TERM: Specific actionable fix for the root cause observed"
  ],
  "performance_insights": [
    "Specific monitoring/alerting improvement tied to the failure pattern found — not generic advice"
  ],
  "severity": "Warning",
  "confidence_score": 0.9
}}

RULES (violations make the response useless):
  - Use real names from the logs; never output <pod-name>, <namespace>, or invented names
  - resolutions must start with IMMEDIATE:  |  config_issues must start with LONG-TERM:
  - severity must be exactly: Critical, Warning, or Healthy
  - No kubectl commands when logs contain no Kubernetes context"""

        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ]

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