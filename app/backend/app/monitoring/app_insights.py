"""
Application Insights integration for monitoring and telemetry
"""
import os
from typing import Optional
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
import logging

class AppInsightsConfig:
    """Configuration for Application Insights"""
    
    def __init__(self):
        self.connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        self.enabled = bool(self.connection_string)
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.service_name = "compliance-iq-backend"
        
        # Sampling rate: 100% for dev, 10% for production
        self.sampling_rate = 1.0 if self.environment == "development" else 0.1
        
        self.tracer: Optional[Tracer] = None
        
    def initialize(self) -> None:
        """Initialize Application Insights exporters"""
        if not self.enabled:
            print("Application Insights: connection string not set. Telemetry disabled.")
            return
            
        try:
            # Initialize trace exporter
            trace_exporter = AzureExporter(
                connection_string=self.connection_string
            )
            
            # Create tracer with sampling
            self.tracer = Tracer(
                exporter=trace_exporter,
                sampler=ProbabilitySampler(self.sampling_rate)
            )
            
            # NOTE: AzureLogHandler is intentionally not added — it is incompatible
            # with Python 3.14 due to the logging lock laziness change. Trace
            # exporting still works; log forwarding to App Insights is skipped locally.
            
            print(f"[INFO] Application Insights initialized (service={self.service_name}, env={self.environment})")
            
        except Exception as e:
            print(f"[WARN] Failed to initialize Application Insights: {e}")
            self.enabled = False
    
    def get_tracer(self) -> Optional[Tracer]:
        """Get the configured tracer"""
        return self.tracer


# Global instance
app_insights = AppInsightsConfig()
