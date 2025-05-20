import time
import random
from typing import List, Dict, Any, Optional
from ec2 import EC2Instance
from security_group import SecurityGroup
from warm_pool_asg import WarmPool


class LaunchTemplate:
    """Defines configuration for EC2 instances launched by an Auto Scaling Group"""

    def __init__(self, template_id: str, instance_type: str, ami_id: str,
                 security_groups: Optional[List[SecurityGroup]] = None):
        self.template_id = template_id
        self.instance_type = instance_type
        self.ami_id = ami_id
        self.security_groups = security_groups or []

    def create_instance(self, instance_id: str) -> EC2Instance:
        """Create a new EC2 instance based on this template"""
        instance = EC2Instance(instance_id, self.instance_type, self.ami_id)
        for sg in self.security_groups:
            instance.attach_security_group(sg)
        return instance


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


class HealthCheck:
    """Simulates AWS health checks for instances"""

    def __init__(self, check_type: str = "EC2", grace_period: int = 300,
                 threshold: int = 2, interval: int = 60):
        self.check_type = check_type  # EC2 or ELB
        self.grace_period = grace_period  # seconds before first check
        self.threshold = threshold  # failures before unhealthy
        self.interval = interval  # seconds between checks

    def check_instance(self, instance: EC2InstanceWithMetrics) -> bool:
        """Perform health check on an instance"""
        if instance.status != "running":
            instance.health_check_count += 1
            if instance.health_check_count >= self.threshold:
                instance.health_status = "unhealthy"
            return False

        # Reset failure count if running
        instance.health_check_count = 0
        instance.health_status = "healthy"
        return True


class ScalingPolicy:
    """Defines when to scale based on metric thresholds"""

    def __init__(self, metric: str, threshold: float, adjustment: int,
                 comparison: str, cooldown: int = 300):
        self.metric = metric  # e.g., "cpu_utilization"
        self.threshold = threshold  # e.g., 70.0 for 70%
        self.adjustment = adjustment  # instances to add/remove
        self.comparison = comparison  # "greater" or "less"
        self.cooldown = cooldown  # seconds between scaling actions
        self.last_scaled_time = 0

    def should_scale(self, current_value: float, current_time: float) -> bool:
        """Check if scaling should occur based on metric value"""
        # Check cooldown period
        if current_time - self.last_scaled_time < self.cooldown:
            return False

        # Check threshold
        if self.comparison == "greater" and current_value > self.threshold:
            self.last_scaled_time = current_time
            return True
        elif self.comparison == "less" and current_value < self.threshold:
            self.last_scaled_time = current_time
            return True

        return False


class AutoScalingGroup:
    # Modify the __init__ method to include warm pool support
    def __init__(self, name: str, launch_template: LaunchTemplate,
                 min_size: int = 1, max_size: int = 5, desired_capacity: int = 2,
                 warm_pool_size: int = 0, warm_pool_min_size: int = 0,
                 instance_reuse_policy: str = "oldest_first"):
        self.name = name
        self.launch_template = launch_template
        self.min_size = min_size
        self.max_size = max_size
        self.desired_capacity = desired_capacity
        self.instances: List[EC2InstanceWithMetrics] = []
        self.scale_out_policies: List[ScalingPolicy] = []
        self.scale_in_policies: List[ScalingPolicy] = []
        self.health_check = HealthCheck()

        # Initialize warm pool if size > 0
        self.warm_pool = None
        if warm_pool_size > 0:
            self.warm_pool = WarmPool(
                size=warm_pool_size,
                min_size=warm_pool_min_size,
                instance_reuse_policy=instance_reuse_policy
            )

    # Modify the start method to initialize warm pool
    def start(self) -> None:
        """Initialize the ASG with the desired capacity and warm pool if configured"""
        print(f"Starting Auto Scaling Group '{self.name}' with {self.desired_capacity} instances")

        # Initialize warm pool if configured
        if self.warm_pool:
            self.warm_pool.initialize(self.launch_template, self.name)

        # Start desired capacity
        for i in range(self.desired_capacity):
            self._add_instance()

    # Modify _add_instance to use warm pool instances when available
    def _add_instance(self) -> Optional[EC2InstanceWithMetrics]:
        """Create and start a new instance, using warm pool if available"""
        if len(self.instances) >= self.max_size:
            print(f"Cannot add instance: at maximum capacity ({self.max_size})")
            return None

        # Check if we have warm instances available
        if self.warm_pool and self.warm_pool.instances:
            # Get instance from warm pool
            warm_instances = self.warm_pool.get_instances(1)
            if warm_instances:
                instance = warm_instances[0]
                self.instances.append(instance)
                print(f"Added warm instance {instance.resource_id} to ASG {self.name}")
                return instance

        # No warm instances, create a new one (use existing implementation)
        instance_id = f"{self.name}-instance-{len(self.instances) + 1}"
        base_instance = self.launch_template.create_instance(instance_id)

        instance = EC2InstanceWithMetrics(
            instance_id=base_instance.resource_id,
            instance_type=base_instance.instance_type,
            ami_id=base_instance.ami_id
        )

        for sg in base_instance.security_groups:
            instance.attach_security_group(sg)

        instance.start()
        self.instances.append(instance)
        print(f"Added new instance {instance_id} to ASG {self.name}")
        return instance

    # Modify _remove_instance to recycle instances to warm pool
    def _remove_instance(self) -> Optional[EC2InstanceWithMetrics]:
        """Remove an instance from the group, potentially adding to warm pool"""
        if len(self.instances) <= self.min_size:
            print(f"Cannot remove instance: at minimum capacity ({self.min_size})")
            return None

        # Find the instance with the lowest load to remove
        instance = min(self.instances, key=lambda i: i.metrics["cpu_utilization"])
        self.instances.remove(instance)

        # If warm pool exists, add the instance to it instead of stopping
        if self.warm_pool and self.warm_pool.size > len(self.warm_pool.instances):
            self.warm_pool.add_instances([instance])
            print(f"Moved instance {instance.resource_id} to warm pool")
        else:
            # No warm pool or it's full, so stop the instance
            instance.stop()
            print(f"Removed instance {instance.resource_id} from ASG {self.name}")

        return instance

    # Update get_status to include warm pool status
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the ASG including warm pool if configured"""
        status = {
            "name": self.name,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "desired_capacity": self.desired_capacity,
            "current_size": len(self.instances),
            "instances": [
                {
                    "id": i.resource_id,
                    "status": i.status,
                    "health": i.health_status,
                    "cpu": i.metrics["cpu_utilization"]
                } for i in self.instances
            ]
        }

        # Add warm pool status if configured
        if self.warm_pool:
            status["warm_pool"] = self.warm_pool.get_status()

        return status

    # Update stop to clean up warm pool
    def stop(self) -> None:
        """Stop all instances and clean up including warm pool"""
        print(f"Stopping Auto Scaling Group '{self.name}'")
        for instance in self.instances:
            instance.stop()
        self.instances = []

        # Stop warm pool if configured
        if self.warm_pool:
            self.warm_pool.stop()