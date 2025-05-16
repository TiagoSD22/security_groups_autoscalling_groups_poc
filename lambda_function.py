from resource import Resource


class LambdaFunction(Resource):
    """Lambda function resource that can have security groups attached"""

    def __init__(self, function_name: str, runtime: str, memory_size: int = 128, timeout: int = 3):
        super().__init__(f"lambda-{function_name}")
        self.function_name = function_name
        self.runtime = runtime
        self.memory_size = memory_size
        self.timeout = timeout

    def invoke(self, payload: dict) -> dict:
        """Simulate invoking the Lambda function"""
        print(f"Invoking Lambda function {self.function_name}")
        return {"statusCode": 200, "body": f"Function {self.function_name} executed successfully"}