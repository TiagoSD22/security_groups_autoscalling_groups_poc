from lambda_function import LambdaFunction
from security_group import SecurityGroup
from security_group_rule import Protocol, Traffic
from ec2 import EC2Instance

from rds import RDSInstance


def print_traffic_result(resource, traffic, is_inbound=True):
    """Helper to print traffic validation results"""
    direction = "inbound" if is_inbound else "outbound"
    allowed = resource.can_receive_traffic(traffic) if is_inbound else resource.can_send_traffic(traffic)
    result = "ALLOWED" if allowed else "DENIED"

    print(f"{direction.upper()} TRAFFIC: {traffic.source_ip}:{traffic.port} -> {traffic.destination_ip} "
          f"(Protocol: {traffic.protocol.name}) - {result}")


def main():
    # Create security groups with different rules
    web_sg = SecurityGroup("sg-001", "web-sg", "Allows HTTP/HTTPS traffic")
    web_sg.add_ingress_rule(Protocol.TCP, 80, 80, "0.0.0.0/0")  # HTTP
    web_sg.add_ingress_rule(Protocol.TCP, 443, 443, "0.0.0.0/0")  # HTTPS

    admin_sg = SecurityGroup("sg-002", "admin-sg", "Allows SSH access")
    admin_sg.add_ingress_rule(Protocol.TCP, 22, 22, "10.0.0.0/8")  # SSH only from internal network

    db_sg = SecurityGroup("sg-003", "db-sg", "Database access")
    db_sg.add_ingress_rule(Protocol.TCP, 3306, 3306, "10.0.0.0/8")  # MySQL from internal network

    internal_sg = SecurityGroup("sg-004", "internal", "Internal network traffic")
    internal_sg.add_ingress_rule(Protocol.ALL, -1, -1, "10.0.0.0/8")

    # Create specific resources
    web_server = EC2Instance("i-web01", "t2.micro", "ami-12345")
    admin_server = EC2Instance("i-admin01", "t2.small", "ami-67890")

    db_instance = RDSInstance("db-mysql-01", "mysql", "8.0.28", "10.0.0.20", 3306)

    api_lambda = LambdaFunction("api-handler", "python3.9", memory_size=256, timeout=10)

    # Attach security groups to resources
    web_server.attach_security_group(web_sg)
    admin_server.attach_security_group(admin_sg)
    admin_server.attach_security_group(internal_sg)  # Admin server has two security groups
    db_instance.attach_security_group(db_sg)
    api_lambda.attach_security_group(internal_sg)

    # Start our instances
    web_server.start()
    admin_server.start()

    print("=== Security Group Traffic Validation ===")

    # Test cases for web server (HTTP/HTTPS only)
    print("\nWeb Server (HTTP/HTTPS only):")
    print_traffic_result(web_server, Traffic("203.0.113.10", "10.0.0.5", Protocol.TCP, 80))  # HTTP allowed
    print_traffic_result(web_server, Traffic("203.0.113.10", "10.0.0.5", Protocol.TCP, 443))  # HTTPS allowed
    print_traffic_result(web_server, Traffic("203.0.113.10", "10.0.0.5", Protocol.TCP, 22))  # SSH denied
    print_traffic_result(web_server, Traffic("203.0.113.10", "10.0.0.5", Protocol.TCP, 8080))  # Alt HTTP denied

    # Test cases for admin server (SSH from internal only)
    print("\nAdmin Server (SSH from internal only):")
    print_traffic_result(admin_server, Traffic("10.0.0.5", "10.0.0.6", Protocol.TCP, 22))  # Internal SSH allowed
    print_traffic_result(admin_server, Traffic("203.0.113.10", "10.0.0.6", Protocol.TCP, 22))  # External SSH denied
    # Internal server can receive all traffic from internal network thanks to internal_sg
    print_traffic_result(admin_server, Traffic("10.0.0.5", "10.0.0.6", Protocol.TCP, 8080))  # Internal traffic allowed

    # Test cases for database (MySQL from internal only)
    print("\nDatabase Server (MySQL from internal only):")
    mysql_traffic_internal = Traffic("10.0.0.5", db_instance.endpoint, Protocol.TCP, db_instance.port)
    mysql_traffic_external = Traffic("203.0.113.10", db_instance.endpoint, Protocol.TCP, db_instance.port)

    print(f"Connection attempt from 10.0.0.5 to MySQL DB: " +
          ("SUCCESS" if db_instance.can_receive_traffic(mysql_traffic_internal) else "FAILED"))
    print(f"Connection attempt from 203.0.113.10 to MySQL DB: " +
          ("SUCCESS" if db_instance.can_receive_traffic(mysql_traffic_external) else "FAILED"))

    # Test Lambda function
    print("\nLambda Function (with internal security group):")
    lambda_traffic = Traffic("10.0.0.5", "10.0.0.30", Protocol.TCP, 443)
    external_lambda_traffic = Traffic("203.0.113.10", "10.0.0.30", Protocol.TCP, 443)

    print_traffic_result(api_lambda, lambda_traffic)  # Internal traffic allowed
    print_traffic_result(api_lambda, external_lambda_traffic)  # External traffic denied

    response = api_lambda.invoke({"action": "test"})
    print(f"Lambda invocation response: {response}")

    web_server.stop()
    admin_server.stop()


if __name__ == "__main__":
    main()