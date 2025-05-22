from typing import Dict
from ec2 import EC2Instance

class EC2InstanceWithMetrics(EC2Instance):
    """Extended EC2 instance that tracks metrics for scaling decisions"""

    def __init__(self, instance_id: str, instance_type: str, ami_id: str):
        super().__init__(instance_id, instance_type, ami_id)
        self.metrics = {
            "cpu_utilization": 0,
            "memory_utilization": 0,
            "network_in": 0,
            "network_out": 0
        }
        self.health_status = "healthy"
        self.health_check_count = 0

    def update_metric(self, name: str, value: float) -> None:
        """Update a specific metric value"""
        if name in self.metrics:
            self.metrics[name] = value

    def get_metrics(self) -> Dict[str, float]:
        """Get all current metrics"""
        return self.metrics

    def is_healthy(self) -> bool:
        """Check if the instance is healthy"""
        return self.status == "running" and self.health_status == "healthy"

    def simulate_load(self, cpu_load: float) -> None:
        """Simulate CPU load on the instance"""
        self.update_metric("cpu_utilization", cpu_load)
