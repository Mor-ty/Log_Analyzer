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
        
        # Try LLM if configured, but rely on enhanced rule-based analysis
        if self.client:
            try:
                prompt = self._build_smart_prompt(condensed_context, analysis_type)
                print("Attempting LLM analysis...")
                response = self.client.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=1500,
                    )
                )
                
                print(f"LLM response received, attempting to parse...")
                result = self._parse_response(response.text)
                if result.get("confidence_score", 0) > 0.6:  # If high confidence, use LLM result
                    print("Using LLM analysis result (high confidence)")
                    return result
                else:
                    print("LLM confidence low, using enhanced rule-based analysis")
                    return self._enhanced_fallback_analysis(log_entries, condensed_context)
            except Exception as e:
                print(f"LLM analysis failed: {e}")
                return self._enhanced_fallback_analysis(log_entries, condensed_context)
        else:
            print("LLM not configured, using enhanced rule-based analysis")
            return self._enhanced_fallback_analysis(log_entries, condensed_context)
    
    def _prepare_condensed_context(self, log_entries: List[Dict]) -> str:
        """Prepare condensed context by extracting only relevant information."""
        
        # Separate entries by severity (handle both enum and string formats)
        critical_errors = [e for e in log_entries if str(e.get('level')) in ['ERROR', 'CRITICAL', 'LogLevel.ERROR', 'LogLevel.CRITICAL']]
        warnings = [e for e in log_entries if str(e.get('level')) in ['WARNING', 'LogLevel.WARNING']]
        stack_traces = self._extract_stack_traces(log_entries)
        
        # Deduplicate messages
        deduplicated_errors = self._deduplicate_messages(critical_errors)
        deduplicated_warnings = self._deduplicate_messages(warnings)
        
        # Build condensed context
        context_parts = []
        
        # Timeline summary
        context_parts.append("=== TIMELINE SUMMARY ===")
        context_parts.append(f"Total entries: {len(log_entries)}")
        context_parts.append(f"Critical errors: {len(critical_errors)}")
        context_parts.append(f"Warnings: {len(warnings)}")
        if log_entries:
            first_timestamp = log_entries[0].get('timestamp')
            last_timestamp = log_entries[-1].get('timestamp')
            if first_timestamp and last_timestamp:
                context_parts.append(f"Time range: {first_timestamp} to {last_timestamp}")
        
        # Top 15 critical failures (deduplicated)
        context_parts.append("\n=== TOP 15 CRITICAL FAILURES ===")
        top_errors = deduplicated_errors[:15]
        for i, entry in enumerate(top_errors, 1):
            timestamp = entry.get('timestamp', 'N/A')
            message = entry.get('message', 'N/A')[:150]  # Truncate long messages
            context_parts.append(f"{i}. [{timestamp}] {message}")
        
        # Repeated patterns
        context_parts.append("\n=== REPEATED PATTERNS ===")
        error_patterns = Counter([e.get('message', '')[:80] for e in critical_errors])
        warning_patterns = Counter([e.get('message', '')[:80] for e in warnings])
        
        context_parts.append("Most common errors:")
        for pattern, count in error_patterns.most_common(5):
            context_parts.append(f"  - {count}x: {pattern}")
        
        context_parts.append("Most common warnings:")
        for pattern, count in warning_patterns.most_common(5):
            context_parts.append(f"  - {count}x: {pattern}")
        
        # Stack traces (limited)
        if stack_traces:
            context_parts.append("\n=== STACK TRACES (First 3) ===")
            for i, trace in enumerate(stack_traces[:3], 1):
                context_parts.append(f"{i}. {trace[:200]}...")
        
        # Anomalies (unusual patterns)
        context_parts.append("\n=== ANOMALIES ===")
        anomalies = self._detect_anomalies(log_entries)
        for anomaly in anomalies[:10]:
            context_parts.append(f"- {anomaly}")
        
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
        """Provide enhanced analysis using smart parsing data."""
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
        
        # Use smart parsing results - handle both enum and string formats
        critical_errors = [e for e in log_entries if str(e.get('level')) in ['ERROR', 'CRITICAL', 'LogLevel.ERROR', 'LogLevel.CRITICAL']]
        warnings = [e for e in log_entries if str(e.get('level')) in ['WARNING', 'LogLevel.WARNING']]
        
        anomalies = []
        root_causes = []
        resolutions = []
        config_issues = []
        performance_insights = []
        
        # Parse the condensed context for insights
        context_lines = condensed_context.split('\n')
        
        # Extract timeline summary info
        for line in context_lines:
            if "Critical errors:" in line:
                errors_count = line.split(':')[-1].strip()
                anomalies.append(f"Found {errors_count} critical error(s)")
            if "Warnings:" in line:
                warnings_count = line.split(':')[-1].strip()
                anomalies.append(f"Found {warnings_count} warning(s)")
        
        # Extract repeated patterns from condensed context
        in_repeated_patterns = False
        for line in context_lines:
            if "REPEATED PATTERNS" in line:
                in_repeated_patterns = True
            elif in_repeated_patterns and line.strip().startswith("-"):
                pattern_info = line.strip()[1:]
                anomalies.append(f"Repeated pattern detected: {pattern_info}")
        
        # Analyze error messages for intelligent insights
        error_messages = [e.get('message', '') for e in critical_errors]
        if error_messages:
            # Check for connection issues
            connection_issues = sum(1 for msg in error_messages if 'connection' in msg.lower())
            if connection_issues > 0:
                root_causes.append("Database or service connectivity problems")
                resolutions.append("Check network connectivity and service endpoints")
                config_issues.append("Potential service endpoint or network configuration issue")
            
            # Check for timeout issues
            timeout_issues = sum(1 for msg in error_messages if 'timeout' in msg.lower())
            if timeout_issues > 0:
                root_causes.append("Service response time exceeding thresholds")
                resolutions.append("Increase timeout values or check service performance")
                performance_insights.append("Service response time issues detected")
            
            # Check for configuration issues
            config_related = sum(1 for msg in error_messages if 'config' in msg.lower())
            if config_related > 0:
                root_causes.append("Application or infrastructure configuration problems")
                resolutions.append("Review application configuration files and environment variables")
                config_issues.append("Configuration-related errors detected")
            
            # Check for memory/resource issues
            resource_issues = sum(1 for msg in error_messages if 'memory' in msg.lower() or 'resource' in msg.lower())
            if resource_issues > 0:
                root_causes.append("Insufficient system resources or memory leaks")
                resolutions.append("Check memory usage and consider increasing resource limits")
                performance_insights.append("Resource pressure detected - consider scaling")
        
        # Generate health assessment
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
        
        # Add insights from condensed context
        if "INFO level logs" not in condensed_context:
            anomalies.append("Application may be running in ERROR-only mode")
            root_causes.append("Logging level misconfiguration - INFO logs not present")
            resolutions.append("Review application logging configuration")
        
        # Add recommendations based on error count
        if len(critical_errors) > 10:
            resolutions.append("Urgent: Multiple critical failures suggest systemic issues")
        elif len(critical_errors) > 5:
            resolutions.append("Review critical errors immediately - may indicate widespread problems")
        
        return {
            "anomalies": anomalies or ["No significant anomalies detected"],
            "root_causes": root_causes or ["No obvious root causes identified"],
            "resolutions": resolutions or ["Review logs for specific issues and patterns"],
            "health_assessment": health,
            "config_issues": config_issues,
            "performance_insights": performance_insights,
            "severity": severity,
            "confidence_score": 0.7  # High confidence in rule-based analysis
        }
    
    def _build_smart_prompt(self, condensed_context: str, analysis_type: str) -> str:
        """Build optimized prompt for condensed context."""
        system_instruction = """You are a senior DevOps engineer specializing in Kubernetes log analysis. Analyze the condensed log summary and provide actionable insights."""
        
        base_prompt = f"""{system_instruction}

Analyze the following condensed Kubernetes log summary:

{condensed_context}

Provide analysis focusing on:
1. **Critical Issues**: Most urgent problems requiring immediate attention
2. **Root Causes**: Underlying causes of the patterns detected
3. **Impact Assessment**: Business and operational impact
4. **Actionable Fixes**: Specific steps to resolve issues
5. **Severity**: Overall assessment (Critical/Warning/Normal)

Provide your response in this JSON format:
{{
    "anomalies": ["anomaly1", "anomaly2"],
    "root_causes": ["cause1", "cause2"], 
    "resolutions": ["fix1", "fix2"],
    "health_assessment": "Overall health summary",
    "config_issues": ["config1", "config2"],
    "performance_insights": ["perf1", "perf2"],
    "severity": "Critical|Warning|Normal",
    "confidence_score": 0.0-1.0
}}

Be concise and focus on actionable recommendations."""
        
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
                            parsed[field] = "Normal"
                        elif field == "confidence_score":
                            parsed[field] = 0.5
                        else:
                            parsed[field] = []
                
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