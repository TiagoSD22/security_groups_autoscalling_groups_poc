import random
from typing import Dict, Any, List

from auto_scalling_group import EC2InstanceWithMetrics, LaunchTemplate


class WarmPool:
    """Maintains a pool of pre-initialized EC2 instances that can quickly join an ASG"""

    def __init__(self, size: int = 0, min_size: int = 0, instance_reuse_policy: str = "oldest_first"):
        self.size = size  # Target size of warm pool
        self.min_size = min_size  # Minimum size to maintain
        self.instance_reuse_policy = instance_reuse_policy  # Strategy for selecting instances
        self.instances: List[EC2InstanceWithMetrics] = []  # Instances in warm pool
        self.state = "stopped"  # State of the warm pool

    def initialize(self, launch_template: LaunchTemplate, asg_name: str) -> None:
        """Initialize the warm pool with the specified number of instances"""
        self.state = "initializing"
        for i in range(self.size):
            instance_id = f"{asg_name}-warm-instance-{i + 1}"
            base_instance = launch_template.create_instance(instance_id)

            instance = EC2InstanceWithMetrics(
                instance_id=base_instance.resource_id,
                instance_type=base_instance.instance_type,
                ami_id=base_instance.ami_id
            )

            # Copy security groups
            for sg in base_instance.security_groups:
                instance.attach_security_group(sg)

            # Initialize but keep in stopped state
            instance.status = "stopped"
            self.instances.append(instance)

        self.state = "ready"
        print(f"Warm pool initialized with {len(self.instances)} instances")

    def get_instances(self, count: int) -> List[EC2InstanceWithMetrics]:
        """Get specified number of instances from the warm pool"""
        if count <= 0 or not self.instances:
            return []

        count = min(count, len(self.instances))

        # Select instances based on policy
        if self.instance_reuse_policy == "oldest_first":
            instances_to_use = self.instances[:count]
        elif self.instance_reuse_policy == "newest_first":
            instances_to_use = self.instances[-count:]
        else:
            # Random selection
            random.shuffle(self.instances)
            instances_to_use = self.instances[:count]

        # Remove from warm pool
        for instance in instances_to_use:
            self.instances.remove(instance)
            # Start the instance
            instance.start()

        print(f"Retrieved {len(instances_to_use)} instances from warm pool")
        return instances_to_use

    def add_instances(self, instances: List[EC2InstanceWithMetrics]) -> None:
        """Add instances to the warm pool"""
        for instance in instances:
            # Keep the instance but stop it
            instance.stop()
            # Mark as warm instance
            instance.status = "stopped"
            self.instances.append(instance)

        print(f"Added {len(instances)} instances to warm pool")

    def maintain_size(self, launch_template: LaunchTemplate, asg_name: str) -> None:
        """Ensure the warm pool maintains its target size"""
        instances_needed = max(0, self.size - len(self.instances))

        if instances_needed > 0:
            print(f"Replenishing warm pool with {instances_needed} new instances")
            for i in range(instances_needed):
                instance_id = f"{asg_name}-warm-instance-{len(self.instances) + i + 1}"
                base_instance = launch_template.create_instance(instance_id)

                instance = EC2InstanceWithMetrics(
                    instance_id=base_instance.resource_id,
                    instance_type=base_instance.instance_type,
                    ami_id=base_instance.ami_id
                )

                for sg in base_instance.security_groups:
                    instance.attach_security_group(sg)

                instance.status = "stopped"
                self.instances.append(instance)

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the warm pool"""
        return {
            "state": self.state,
            "size": self.size,
            "current_size": len(self.instances),
            "min_size": self.min_size,
            "reuse_policy": self.instance_reuse_policy
        }

    def stop(self) -> None:
        """Stop and clean up the warm pool"""
        for instance in self.instances:
            instance.terminate() if hasattr(instance, 'terminate') else instance.stop()

        self.instances = []
        self.state = "stopped"
        print("Warm pool stopped and instances terminated")