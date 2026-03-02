"""
Custom metrics tracking for Application Insights
"""
import time
from contextlib import contextmanager
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class MetricsTracker:
    """Track custom metrics for business intelligence"""
    
    def __init__(self):
        self.enabled = True
    
    def track_metric(self, name: str, value: float, properties: Dict[str, Any] = None) -> None:
        """
        Track a custom metric.
        
        Args:
            name: Metric name
            value: Metric value
            properties: Additional properties/dimensions
        """
        if not self.enabled:
            return
            
        log_data = {
            "metric_name": name,
            "metric_value": value,
            "metric_type": "custom"
        }
        
        if properties:
            log_data.update(properties)
            
        logger.info("custom_metric", extra=log_data)
    
    def track_mapping_duration(self, duration_ms: float, control_id: str, success: bool) -> None:
        """Track AI mapping operation duration"""
        self.track_metric(
            "mapping.duration_ms",
            duration_ms,
            {
                "control_id": control_id,
                "success": success
            }
        )
    
    def track_openai_usage(self, prompt_tokens: int, completion_tokens: int, 
                          model: str, duration_ms: float) -> None:
        """Track OpenAI API usage"""
        total_tokens = prompt_tokens + completion_tokens
        
        self.track_metric("openai.prompt_tokens", prompt_tokens, {"model": model})
        self.track_metric("openai.completion_tokens", completion_tokens, {"model": model})
        self.track_metric("openai.total_tokens", total_tokens, {"model": model})
        self.track_metric("openai.request_duration_ms", duration_ms, {"model": model})
        
        # Estimate cost (example rates, adjust based on actual pricing)
        prompt_cost = (prompt_tokens / 1000) * 0.01  # $0.01 per 1K tokens
        completion_cost = (completion_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        total_cost = prompt_cost + completion_cost
        
        self.track_metric("openai.cost_estimate_usd", total_cost, {"model": model})
    
    def track_cosmosdb_operation(self, operation: str, ru_consumed: float, 
                                 duration_ms: float, success: bool) -> None:
        """Track Cosmos DB operation metrics"""
        self.track_metric(
            "cosmosdb.ru_consumed",
            ru_consumed,
            {
                "operation": operation,
                "success": success
            }
        )
        
        self.track_metric(
            "cosmosdb.query_duration_ms",
            duration_ms,
            {
                "operation": operation,
                "success": success
            }
        )
    
    def track_auth_event(self, event_type: str, success: bool, user_id: str = None) -> None:
        """Track authentication events"""
        properties = {
            "event_type": event_type,
            "success": success
        }
        
        if user_id:
            properties["user_id"] = user_id
            
        self.track_metric(
            f"auth.{event_type}",
            1.0,  # Counter
            properties
        )
    
    @contextmanager
    def track_duration(self, operation_name: str, properties: Dict[str, Any] = None):
        """
        Context manager to track operation duration.
        
        Usage:
            with metrics.track_duration("my_operation", {"param": "value"}):
                # Do work
                pass
        """
        start_time = time.time()
        exception_raised = False
        
        try:
            yield
        except Exception:
            exception_raised = True
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            props = properties or {}
            props["success"] = not exception_raised
            
            self.track_metric(
                f"{operation_name}.duration_ms",
                duration_ms,
                props
            )


# Global metrics tracker instance
metrics = MetricsTracker()
