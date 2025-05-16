from enum import Enum
from typing import List
import ipaddress


class Protocol(Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ALL = "-1"


class IpRange:
    def __init__(self, cidr: str):
        self.cidr = cidr

    def contains(self, ip: str) -> bool:
        """Check if the IP address is in this CIDR range"""
        return ipaddress.ip_address(ip) in ipaddress.ip_network(self.cidr)


class SecurityGroupRule:
    def __init__(self, protocol: Protocol, from_port: int, to_port: int,
                 ip_ranges: List[IpRange], is_egress: bool):
        self.protocol = protocol
        self.from_port = from_port  # -1 for ALL
        self.to_port = to_port      # -1 for ALL
        self.ip_ranges = ip_ranges
        self.is_egress = is_egress  # True for outbound, False for inbound

    def matches_traffic(self, protocol: Protocol, port: int, ip: str) -> bool:
        """Check if traffic matches this rule"""
        if self.protocol != protocol and self.protocol != Protocol.ALL:
            return False

        port_match = (self.from_port <= port <= self.to_port) or self.from_port == -1

        if port_match:
            for ip_range in self.ip_ranges:
                if ip_range.contains(ip):
                    return True

        return False


class Traffic:
    """Represents network traffic"""
    def __init__(self, source_ip: str, destination_ip: str, protocol: Protocol, port: int):
        self.source_ip = source_ip
        self.destination_ip = destination_ip
        self.protocol = protocol
        self.port = port