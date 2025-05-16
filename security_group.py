from typing import List

from security_group_rule import Traffic, SecurityGroupRule, Protocol, IpRange


class SecurityGroup:
    """Implementation of a security group"""
    def __init__(self, group_id: str, name: str, description: str = ""):
        self.group_id = group_id
        self.name = name
        self.description = description
        self.inbound_rules: List[SecurityGroupRule] = []
        self.outbound_rules: List[SecurityGroupRule] = []

        # By default, allow all outbound traffic
        self.add_egress_rule(Protocol.ALL, -1, -1, "0.0.0.0/0")

    def get_id(self) -> str:
        return self.group_id

    def add_ingress_rule(self, protocol: Protocol, from_port: int, to_port: int, cidr: str) -> None:
        self.inbound_rules.append(
            SecurityGroupRule(
                protocol=protocol,
                from_port=from_port,
                to_port=to_port,
                ip_ranges=[IpRange(cidr)],
                is_egress=False
            )
        )

    def add_egress_rule(self, protocol: Protocol, from_port: int, to_port: int, cidr: str) -> None:
        self.outbound_rules.append(
            SecurityGroupRule(
                protocol=protocol,
                from_port=from_port,
                to_port=to_port,
                ip_ranges=[IpRange(cidr)],
                is_egress=True
            )
        )

    def allow_inbound_traffic(self, traffic: Traffic) -> bool:
        """Check if inbound traffic is allowed"""
        for rule in self.inbound_rules:
            if rule.matches_traffic(traffic.protocol, traffic.port, traffic.source_ip):
                return True
        return False

    def allow_outbound_traffic(self, traffic: Traffic) -> bool:
        """Check if outbound traffic is allowed
        Implements stateful behavior - if inbound traffic was allowed,
        the corresponding response is automatically allowed
        """
        # First check for stateful return traffic
        reverse_traffic = Traffic(
            source_ip=traffic.destination_ip,
            destination_ip=traffic.source_ip,
            protocol=traffic.protocol,
            port=traffic.port
        )

        if self.allow_inbound_traffic(reverse_traffic):
            return True

        # Check explicit outbound rules
        for rule in self.outbound_rules:
            if rule.matches_traffic(traffic.protocol, traffic.port, traffic.destination_ip):
                return True

        return False