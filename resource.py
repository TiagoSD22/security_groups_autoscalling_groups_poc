from typing import List

from security_group import SecurityGroup
from security_group_rule import Traffic


class Resource:
    """Implementation of a resource with security groups"""
    def __init__(self, resource_id: str):
        self.resource_id = resource_id
        self.security_groups: List[SecurityGroup] = []

    def attach_security_group(self, security_group: SecurityGroup) -> None:
        self.security_groups.append(security_group)

    def detach_security_group(self, security_group_id: str) -> None:
        self.security_groups = [sg for sg in self.security_groups if sg.get_id() != security_group_id]

    def get_security_groups(self) -> List[SecurityGroup]:
        return self.security_groups

    def can_receive_traffic(self, traffic: Traffic) -> bool:
        """Traffic is allowed if at least one security group allows it"""
        if not self.security_groups:
            return False

        for sg in self.security_groups:
            if sg.allow_inbound_traffic(traffic):
                return True

        return False

    def can_send_traffic(self, traffic: Traffic) -> bool:
        """Traffic is allowed if at least one security group allows it"""
        if not self.security_groups:
            return False

        for sg in self.security_groups:
            if sg.allow_outbound_traffic(traffic):
                return True

        return False