from typing import List, Optional
from ec2 import EC2Instance
from security_group import SecurityGroup

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
