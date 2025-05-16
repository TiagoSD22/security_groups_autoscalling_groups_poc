from resource import Resource


class EC2Instance(Resource):
    """EC2 Instance resource that can have security groups attached"""

    def __init__(self, instance_id: str, instance_type: str, ami_id: str):
        super().__init__(instance_id)
        self.instance_type = instance_type
        self.ami_id = ami_id
        self.status = "stopped"

    def start(self) -> None:
        """Start the EC2 instance"""
        self.status = "running"
        print(f"EC2 Instance {self.resource_id} started")

    def stop(self) -> None:
        """Stop the EC2 instance"""
        self.status = "stopped"
        print(f"EC2 Instance {self.resource_id} stopped")





