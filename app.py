# app.py
import boto3
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="LocalStack Resource Manager")

# LocalStack endpoint
endpoint_url = "http://localhost:4566"

# Initialize clients
ec2 = boto3.client('ec2', endpoint_url=endpoint_url, region_name='us-east-1',
                   aws_access_key_id='test', aws_secret_access_key='test')
autoscaling = boto3.client('autoscaling', endpoint_url=endpoint_url, region_name='us-east-1',
                           aws_access_key_id='test', aws_secret_access_key='test')

# Load resource IDs
with open('resources.json', 'r') as f:
    resources = json.load(f)


class SecurityGroupRequest(BaseModel):
    security_group_type: str  # "secure" or "open"


class ScalingRequest(BaseModel):
    action: str  # "scale_out", "scale_in", or "set_capacity"
    capacity: int = None


@app.post("/security-group/validate")
def validate_security_group(request: SecurityGroupRequest):
    """Test security group functionality"""
    if request.security_group_type not in ["secure", "open"]:
        raise HTTPException(status_code=400, detail="Type must be 'secure' or 'open'")

    sg_id = resources[f"{request.security_group_type}_sg_id"]

    # Get security group rules
    rules = ec2.describe_security_group_rules(
        Filters=[{'Name': 'group-id', 'Values': [sg_id]}]
    )

    # Analyze open ports
    open_ports = []
    for rule in rules.get('SecurityGroupRules', []):
        if rule.get('IsEgress') == False:  # Ingress rule
            if rule.get('IpProtocol') == '-1':
                open_ports = ["All Ports"]
                break
            from_port = rule.get('FromPort')
            to_port = rule.get('ToPort')
            if from_port == to_port:
                open_ports.append(from_port)
            else:
                open_ports.extend(list(range(from_port, to_port + 1)))

    return {
        "security_group_id": sg_id,
        "security_group_type": request.security_group_type,
        "open_ports": open_ports,
        "is_correctly_configured": (request.security_group_type == "secure" and open_ports == [80]) or
                                   (request.security_group_type == "open" and "All Ports" in open_ports)
    }


@app.post("/autoscaling/trigger")
def trigger_autoscaling(request: ScalingRequest):
    """Trigger autoscaling actions"""
    asg_name = 'app-asg'

    # Get current ASG state
    response = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )

    if not response['AutoScalingGroups']:
        raise HTTPException(status_code=404, detail=f"Auto Scaling Group '{asg_name}' not found")

    asg = response['AutoScalingGroups'][0]
    current_capacity = asg['DesiredCapacity']
    min_size = asg['MinSize']
    max_size = asg['MaxSize']

    if request.action == "scale_out":
        if current_capacity >= max_size:
            return {"message": f"Already at maximum capacity: {current_capacity}", "success": False}

        autoscaling.execute_policy(
            AutoScalingGroupName=asg_name,
            PolicyName='scale-out',
            HonorCooldown=False
        )
        new_capacity = current_capacity + 1

    elif request.action == "scale_in":
        if current_capacity <= min_size:
            return {"message": f"Already at minimum capacity: {current_capacity}", "success": False}

        autoscaling.execute_policy(
            AutoScalingGroupName=asg_name,
            PolicyName='scale-in',
            HonorCooldown=False
        )
        new_capacity = current_capacity - 1

    elif request.action == "set_capacity" and request.capacity is not None:
        if request.capacity < min_size or request.capacity > max_size:
            return {"message": f"Capacity must be between {min_size} and {max_size}", "success": False}

        autoscaling.set_desired_capacity(
            AutoScalingGroupName=asg_name,
            DesiredCapacity=request.capacity
        )
        new_capacity = request.capacity

    else:
        raise HTTPException(status_code=400, detail="Invalid action or missing capacity")

    return {
        "previous_capacity": current_capacity,
        "new_capacity": new_capacity,
        "min_size": min_size,
        "max_size": max_size,
        "success": True
    }


@app.get("/status")
def get_status():
    """Get current status of all resources"""
    asg = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=['app-asg'])

    return {
        "security_groups": {
            "secure": resources.get('secure_sg_id'),
            "open": resources.get('open_sg_id')
        },
        "auto_scaling_group": {
            "name": "app-asg",
            "current_capacity": asg['AutoScalingGroups'][0]['DesiredCapacity'] if asg['AutoScalingGroups'] else None,
            "min_size": asg['AutoScalingGroups'][0]['MinSize'] if asg['AutoScalingGroups'] else None,
            "max_size": asg['AutoScalingGroups'][0]['MaxSize'] if asg['AutoScalingGroups'] else None
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)