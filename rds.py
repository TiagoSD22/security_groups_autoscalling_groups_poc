from resource import Resource


class RDSInstance(Resource):
    """RDS Database instance that can have security groups attached"""

    def __init__(self, db_instance_id: str, engine: str, engine_version: str,
                 endpoint: str, port: int):
        super().__init__(db_instance_id)
        self.engine = engine
        self.engine_version = engine_version
        self.endpoint = endpoint
        self.port = port
        self.status = "available"

    def connect(self, source_ip: str) -> bool:
        """Simulate database connection attempt"""
        print(f"Connection from {source_ip} to {self.endpoint}:{self.port} established")
        return True