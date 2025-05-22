import time
import random

from auto_scalling_group import ScalingPolicy, AutoScalingGroup, LaunchTemplate
from security_group import SecurityGroup
from security_group_rule import Protocol


class ASGSimulationApp:
    def __init__(self):
        self.asgs = []

    def create_security_group(self, sg_id, name, description, rules):
        sg = SecurityGroup(sg_id, name, description)
        for rule in rules:
            sg.add_ingress_rule(rule['protocol'], rule['from_port'], rule['to_port'], rule['cidr'])
        return sg

    def create_asg(self, name, template, min_size, max_size, desired_capacity, warm_pool_size=None, warm_pool_min_size=None):
        asg = AutoScalingGroup(
            name=name,
            launch_template=template,
            min_size=min_size,
            max_size=max_size,
            desired_capacity=desired_capacity,
            warm_pool_size=warm_pool_size,
            warm_pool_min_size=warm_pool_min_size
        )
        self.asgs.append(asg)
        return asg

    def simulate_asg(self, asg, cycles=3):
        asg.start()
        try:
            print(f"\nSimulating ASG: {asg.name} (press Ctrl+C to stop)...")
            for i in range(cycles):
                print(f"\n--- Simulation Cycle {i + 1} ---")

                # Generate random load pattern
                if i < 3:
                    load = 50.0  # Normal load
                elif i < 6:
                    load = 85.0  # High load
                else:
                    load = 20.0  # Low load

                print(f"Simulating traffic with base load: {load:.1f}%")
                asg.simulate_traffic(base_load=load)

                asg.evaluate_metrics()
                asg.check_health()

                # Simulate instance failure (20% chance)
                if random.random() < 0.2 and asg.instances:
                    instance = random.choice(asg.instances)
                    print(f"Simulating failure of {instance.resource_id}")
                    instance.status = "stopped"  # Force a failure

                status = asg.get_status()
                print(f"Current ASG status: {status['current_size']}/{status['desired_capacity']} instances")

                if 'warm_pool' in status:
                    warm_pool = status['warm_pool']
                    print(f"Warm pool: {warm_pool['current_size']}/{warm_pool['size']} ready instances")

                time.sleep(2)

        except KeyboardInterrupt:
            print("\nSimulation interrupted")
        finally:
            asg.stop()
            print("Simulation complete")

    def run(self):
        # Example setup for ASG with and without warm pool
        web_sg = self.create_security_group(
            "sg-001", "web-sg", "Allows HTTP/HTTPS traffic",
            [
                {"protocol": Protocol.TCP, "from_port": 80, "to_port": 80, "cidr": "0.0.0.0/0"},
                {"protocol": Protocol.TCP, "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"}
            ]
        )

        template = LaunchTemplate(
            template_id="lt-web-001",
            instance_type="t2.micro",
            ami_id="ami-12345",
            security_groups=[web_sg]
        )

        # Standard ASG
        standard_asg = self.create_asg(
            name="web-servers-standard",
            template=template,
            min_size=1,
            max_size=5,
            desired_capacity=2
        )
        standard_asg.add_scale_out_policy(
            ScalingPolicy("cpu_utilization", 70.0, 1, "greater", cooldown=60)
        )
        standard_asg.add_scale_in_policy(
            ScalingPolicy("cpu_utilization", 30.0, 1, "less", cooldown=60)
        )

        # ASG with warm pool
        warm_pool_asg = self.create_asg(
            name="web-servers-warm-pool",
            template=template,
            min_size=1,
            max_size=5,
            desired_capacity=2,
            warm_pool_size=3,
            warm_pool_min_size=1
        )
        warm_pool_asg.add_scale_out_policy(
            ScalingPolicy("cpu_utilization", 70.0, 2, "greater", cooldown=60)
        )
        warm_pool_asg.add_scale_in_policy(
            ScalingPolicy("cpu_utilization", 30.0, 1, "less", cooldown=60)
        )

        # Simulate both ASGs
        self.simulate_asg(standard_asg)
        self.simulate_asg(warm_pool_asg)


if __name__ == "__main__":
    app = ASGSimulationApp()
    app.run()
