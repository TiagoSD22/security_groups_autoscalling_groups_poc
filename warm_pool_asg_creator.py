import time

from auto_scalling_group import ScalingPolicy, AutoScalingGroup, LaunchTemplate
from security_group import SecurityGroup
from security_group_rule import Protocol


def test_warm_pool():
    """Test the warm pool functionality"""
    # Create security groups
    web_sg = SecurityGroup("sg-001", "web-sg", "Allows HTTP/HTTPS traffic")
    web_sg.add_ingress_rule(Protocol.TCP, 80, 80, "0.0.0.0/0")  # HTTP
    web_sg.add_ingress_rule(Protocol.TCP, 443, 443, "0.0.0.0/0")  # HTTPS

    template = LaunchTemplate(
        template_id="lt-web-001",
        instance_type="t2.micro",
        ami_id="ami-12345",
        security_groups=[web_sg]
    )

    # Create ASG with warm pool of 3 instances
    web_asg = AutoScalingGroup(
        name="web-servers",
        launch_template=template,
        min_size=1,
        max_size=5,
        desired_capacity=2,
        warm_pool_size=3,  # Maintain 3 instances in warm pool
        warm_pool_min_size=1  # Keep at least 1 instance in warm pool
    )

    web_asg.add_scale_out_policy(
        ScalingPolicy("cpu_utilization", 70.0, 2, "greater", cooldown=60)
    )
    web_asg.add_scale_in_policy(
        ScalingPolicy("cpu_utilization", 30.0, 1, "less", cooldown=60)
    )

    web_asg.start()

    try:
        print("\nStarting simulation with warm pool (press Ctrl+C to stop)...")
        for i in range(10):
            print(f"\n--- Simulation Cycle {i + 1} ---")

            # Generate load pattern
            if i < 3:
                # Normal load
                load = 50.0
            elif i < 6:
                # High load - should trigger scale out using warm pool
                load = 85.0
            else:
                # Low load - should trigger scale in
                load = 20.0

            print(f"Simulating traffic with base load: {load:.1f}%")
            web_asg.simulate_traffic(base_load=load)

            web_asg.evaluate_metrics()
            web_asg.check_health()

            # Print status including warm pool
            status = web_asg.get_status()
            print(f"ASG status: {status['current_size']}/{status['desired_capacity']} active instances")

            if 'warm_pool' in status:
                warm_pool = status['warm_pool']
                print(f"Warm pool: {warm_pool['current_size']}/{warm_pool['size']} ready instances")

            # Maintain warm pool size
            if web_asg.warm_pool:
                web_asg.warm_pool.maintain_size(template, web_asg.name)

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nSimulation interrupted")
    finally:
        web_asg.stop()
        print("Simulation complete")