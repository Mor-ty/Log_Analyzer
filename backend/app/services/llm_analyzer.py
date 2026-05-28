import json
from typing import List, Dict, Optional
import google.generativeai as genai
from app.core.config import settings


class LLMLogAnalyzer:
    """Use LLM to analyze logs and provide insights using Google Gemini."""
    
    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            try:
                # Try to use different model names based on API version availability
                self.client = genai.GenerativeModel('gemini-1.0-pro')
            except Exception as e:
                print(f"Failed to initialize gemini-1.0-pro: {e}")
                try:
                    self.client = genai.GenerativeModel('gemini-pro')
                except Exception as e2:
                    print(f"Failed to initialize gemini-pro: {e2}")
                    # Try listing available models
                    try:
                        for model in genai.list_models():
                            if 'generateContent' in model.supported_generation_methods:
                                print(f"Available model: {model.name}")
                                self.client = genai.GenerativeModel(model.name)
                                break
                    except Exception as e3:
                        print(f"Failed to list models: {e3}")
    
    def analyze_logs(
        self, 
        log_entries: List[Dict], 
        analysis_type: str = "general"
    ) -> Dict:
        """Analyze log entries using LLM."""
        print(f"Starting LLM analysis, client configured: {self.client is not None}")
        
        if not self.client:
            print("LLM client not configured, using fallback analysis")
            return self._fallback_analysis(log_entries)
        
        # Prepare log context
        log_context = self._prepare_log_context(log_entries)
        print(f"Prepared log context with {len(log_entries)} entries")
        
        prompt = self._build_prompt(log_context, analysis_type)
        print("Sending prompt to LLM...")
        
        try:
            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1500,
                )
            )
            
            print(f"LLM response received, parsing...")
            result = self._parse_response(response.text)
            print(f"Analysis completed successfully")
            return result
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return self._fallback_analysis(log_entries)
    
    def _prepare_log_context(self, log_entries: List[Dict]) -> str:
        """Prepare log entries for LLM context."""
        # Filter to most relevant entries (errors, warnings, and recent entries)
        error_entries = [e for e in log_entries if e.get('level') in ['ERROR', 'CRITICAL']]
        warning_entries = [e for e in log_entries if e.get('level') == 'WARNING']
        
        # Take last 50 entries to avoid token limits
        recent_entries = log_entries[-50:] if len(log_entries) > 50 else log_entries
        
        context = []
        context.append("=== ERROR LOGS ===")
        for entry in error_entries[:20]:  # Max 20 errors
            context.append(f"[{entry.get('timestamp')}] {entry.get('level')}: {entry.get('message')}")
        
        context.append("\n=== WARNING LOGS ===")
        for entry in warning_entries[:10]:  # Max 10 warnings
            context.append(f"[{entry.get('timestamp')}] {entry.get('level')}: {entry.get('message')}")
        
        context.append("\n=== RECENT LOGS ===")
        for entry in recent_entries:
            context.append(f"[{entry.get('timestamp')}] {entry.get('level')}: {entry.get('message')}")
        
        return "\n".join(context)
    
    def _build_prompt(self, log_context: str, analysis_type: str) -> str:
        """Build the prompt for LLM analysis."""
        system_instruction = """You are a senior DevOps engineer and Kubernetes expert specializing in log analysis and application health monitoring. 
Analyze logs from the perspective of maintaining production systems, identifying health issues, configuration problems, and providing actionable fixes."""
        
        base_prompt = f"""{system_instruction}

Analyze the following Kubernetes application logs and provide a comprehensive DevOps analysis:

## Analysis Requirements:

### 1. Application Health Assessment
- Overall application health status
- Resource utilization patterns (if detectable)
- Application lifecycle events (startup, shutdown, restarts)
- Performance indicators

### 2. Configuration Analysis
- Configuration issues or misconfigurations
- Environment variable problems
- Dependency and service connection issues
- Security-related concerns

### 3. Error Analysis & Impact
- Critical errors and their business impact
- Error patterns and frequency
- Cascading failure risks
- Service dependencies affected

### 4. DevOps Insights & Recommendations
- Specific actionable fixes for each issue
- Kubernetes-specific recommendations (resource limits, probes, etc.)
- Monitoring and alerting suggestions
- Prevention strategies for future issues

### 5. Severity Assessment
- Rate overall severity: Critical, Warning, or Normal
- Consider business impact and user experience
- Factor in error frequency and patterns

## Log Context:
{log_context}

## Response Format:
Provide your analysis in this exact JSON format:
{{
    "anomalies": [
        "Specific anomaly 1 with context",
        "Specific anomaly 2 with context"
    ],
    "root_causes": [
        "Root cause 1 with technical details",
        "Root cause 2 with technical details"
    ],
    "resolutions": [
        "Step-by-step fix for issue 1",
        "Step-by-step fix for issue 2"
    ],
    "health_assessment": "Overall health summary",
    "config_issues": ["Configuration issue 1", "Configuration issue 2"],
    "performance_insights": ["Performance insight 1", "Performance insight 2"],
    "severity": "Critical|Warning|Normal",
    "confidence_score": 0.0-1.0
}}

Focus on actionable, specific guidance that a DevOps engineer can implement immediately."""
        
        if analysis_type == "error_focus":
            base_prompt = base_prompt.replace(
                "Analyze the following Kubernetes logs",
                "Focus specifically on ERROR and CRITICAL logs. Analyze the following Kubernetes logs"
            )
        
        return base_prompt
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse LLM response into structured format."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)
                
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
        """Provide basic rule-based analysis when LLM is unavailable."""
        error_count = sum(1 for e in log_entries if e.get('level') in ['ERROR', 'CRITICAL'])
        warning_count = sum(1 for e in log_entries if e.get('level') == 'WARNING')
        info_count = sum(1 for e in log_entries if e.get('level') == 'INFO')
        
        anomalies = []
        if error_count > 0:
            anomalies.append(f"Found {error_count} error(s) in logs")
        if warning_count > 0:
            anomalies.append(f"Found {warning_count} warning(s) in logs")
        
        # Check for common error patterns
        error_messages = [e.get('message', '') for e in log_entries if e.get('level') in ['ERROR', 'CRITICAL']]
        config_issues = []
        performance_insights = []
        
        resolutions = ["Review error logs above for specific issues"]
        
        if any('connection' in msg.lower() for msg in error_messages):
            resolutions.append("Check network connectivity and service endpoints")
            config_issues.append("Potential service endpoint or network configuration issue")
        if any('timeout' in msg.lower() for msg in error_messages):
            resolutions.append("Increase timeout values or check service performance")
            performance_insights.append("Service response time issues detected")
        if any('memory' in msg.lower() for msg in error_messages):
            resolutions.append("Check memory usage and consider increasing resource limits")
            performance_insights.append("Memory pressure detected - consider increasing limits")
        if any('config' in msg.lower() for msg in error_messages):
            resolutions.append("Review application configuration files")
            config_issues.append("Configuration-related errors detected")
        
        # Health assessment
        if error_count > 5:
            health = "Critical - Multiple errors indicate serious application issues"
        elif error_count > 0:
            health = "Warning - Application has errors that need attention"
        elif warning_count > 3:
            health = "Warning - Multiple warnings suggest potential issues"
        else:
            health = "Normal - Application appears to be running smoothly"
        
        severity = "Critical" if error_count > 5 else "Warning" if error_count > 0 else "Normal"
        
        return {
            "anomalies": anomalies,
            "root_causes": ["Manual analysis required - LLM not configured properly"],
            "resolutions": resolutions,
            "health_assessment": health,
            "config_issues": config_issues,
            "performance_insights": performance_insights,
            "severity": severity,
            "confidence_score": 0.3
        }
