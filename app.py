# app.py
import boto3
import json
import os
import time
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import threading
from collections import deque
from datetime import datetime
import asyncio

app = FastAPI(title="LocalStack Resource Manager")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LocalStack endpoint
endpoint_url = "http://localhost:4566"

# Initialize EC2 client
ec2 = boto3.client('ec2', endpoint_url=endpoint_url, region_name='us-east-1',
                   aws_access_key_id='test', aws_secret_access_key='test')

# Mock autoscaling state file
ASG_STATE_FILE = 'asg_state.json'

# Auto-scaling configuration
SCALING_CONFIG = {
    'scale_out_threshold': 10,  # requests per minute
    'scale_in_threshold': 5,  # requests per minute
    'check_interval': 60,  # seconds
    'cooldown_period': 120  # seconds
}

# Request tracking
request_timestamps = deque(maxlen=1000)  # Store recent request timestamps
last_scale_time = 0  # To track cooldown period


# Initialize or load autoscaling state
def get_asg_state():
    if os.path.exists(ASG_STATE_FILE):
        with open(ASG_STATE_FILE, 'r') as f:
            return json.load(f)
    else:
        # Default state
        state = {
            'app-asg': {
                'DesiredCapacity': 2,
                'MinSize': 1,
                'MaxSize': 5,
                'Instances': [{'InstanceId': f'i-mock{i:03d}'} for i in range(2)],
                'LastScalingTime': 0
            }
        }
        save_asg_state(state)
        return state


def save_asg_state(state):
    with open(ASG_STATE_FILE, 'w') as f:
        json.dump(state, f)


# Load resource IDs
def get_resources():
    if os.path.exists('resources.json'):
        with open('resources.json', 'r') as f:
            return json.load(f)
    else:
        return {}


# Calculate requests per minute
def get_requests_per_minute():
    now = time.time()
    # Count requests in the last minute
    count = sum(1 for ts in request_timestamps if now - ts <= 60)
    return count


# Auto-scaling logic
def check_auto_scaling():
    while True:
        try:
            # Get current request rate
            rpm = get_requests_per_minute()

            # Get ASG state
            asg_state = get_asg_state()
            asg = asg_state['app-asg']
            current_capacity = asg['DesiredCapacity']
            min_size = asg['MinSize']
            max_size = asg['MaxSize']
            last_scaling_time = asg['LastScalingTime']

            now = time.time()
            # Check if we're out of cooldown period
            if now - last_scaling_time >= SCALING_CONFIG['cooldown_period']:
                if rpm >= SCALING_CONFIG['scale_out_threshold'] and current_capacity < max_size:
                    # Scale out
                    asg['DesiredCapacity'] += 1
                    asg['LastScalingTime'] = now
                    asg['Instances'] = [{'InstanceId': f'i-mock{i:03d}'} for i in range(asg['DesiredCapacity'])]
                    print(f"Auto-scaling out to {asg['DesiredCapacity']} instances based on {rpm} requests/min")
                elif rpm <= SCALING_CONFIG['scale_in_threshold'] and current_capacity > min_size:
                    # Scale in
                    asg['DesiredCapacity'] -= 1
                    asg['LastScalingTime'] = now
                    asg['Instances'] = [{'InstanceId': f'i-mock{i:03d}'} for i in range(asg['DesiredCapacity'])]
                    print(f"Auto-scaling in to {asg['DesiredCapacity']} instances based on {rpm} requests/min")

            # Save updated state
            asg_state['app-asg'] = asg
            save_asg_state(asg_state)
        except Exception as e:
            print(f"Error in auto-scaling check: {e}")

        # Wait before next check
        time.sleep(SCALING_CONFIG['check_interval'])


class SecurityGroupRequest(BaseModel):
    security_group_type: str  # "secure" or "open"


class ScalingRequest(BaseModel):
    action: str  # "scale_out", "scale_in", or "set_capacity"
    capacity: int = None


class ScalingConfigRequest(BaseModel):
    scale_out_threshold: int = None
    scale_in_threshold: int = None
    check_interval: int = None
    cooldown_period: int = None


# Request tracking middleware
@app.middleware("http")
async def track_requests(request: Request, call_next):
    # Record request timestamp
    request_timestamps.append(time.time())
    response = await call_next(request)
    return response


@app.post("/security-group/validate")
def validate_security_group(request: SecurityGroupRequest):
    """Test security group functionality"""
    resources = get_resources()

    if request.security_group_type not in ["secure", "open"]:
        raise HTTPException(status_code=400, detail="Type must be 'secure' or 'open'")

    sg_key = f"{request.security_group_type}_sg_id"
    if sg_key not in resources:
        raise HTTPException(status_code=404, detail=f"Security group '{sg_key}' not found")

    sg_id = resources[sg_key]

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
    """Trigger manual autoscaling actions"""
    asg_name = 'app-asg'
    asg_state = get_asg_state()

    if asg_name not in asg_state:
        raise HTTPException(status_code=404, detail=f"Auto Scaling Group '{asg_name}' not found")

    asg = asg_state[asg_name]
    current_capacity = asg['DesiredCapacity']
    min_size = asg['MinSize']
    max_size = asg['MaxSize']

    if request.action == "scale_out":
        if current_capacity >= max_size:
            return {"message": f"Already at maximum capacity: {current_capacity}", "success": False}

        new_capacity = current_capacity + 1
        asg['DesiredCapacity'] = new_capacity
        asg['LastScalingTime'] = time.time()

    elif request.action == "scale_in":
        if current_capacity <= min_size:
            return {"message": f"Already at minimum capacity: {current_capacity}", "success": False}

        new_capacity = current_capacity - 1
        asg['DesiredCapacity'] = new_capacity
        asg['LastScalingTime'] = time.time()

    elif request.action == "set_capacity" and request.capacity is not None:
        if request.capacity < min_size or request.capacity > max_size:
            return {"message": f"Capacity must be between {min_size} and {max_size}", "success": False}

        new_capacity = request.capacity
        asg['DesiredCapacity'] = new_capacity
        asg['LastScalingTime'] = time.time()

    else:
        raise HTTPException(status_code=400, detail="Invalid action or missing capacity")

    # Update mock instance list based on new capacity
    asg['Instances'] = [{'InstanceId': f'i-mock{i:03d}'} for i in range(new_capacity)]

    # Save updated state
    asg_state[asg_name] = asg
    save_asg_state(asg_state)

    return {
        "previous_capacity": current_capacity,
        "new_capacity": new_capacity,
        "min_size": min_size,
        "max_size": max_size,
        "success": True
    }


@app.post("/autoscaling/config")
def update_scaling_config(request: ScalingConfigRequest):
    """Update auto-scaling configuration"""
    global SCALING_CONFIG

    if request.scale_out_threshold is not None:
        SCALING_CONFIG['scale_out_threshold'] = request.scale_out_threshold

    if request.scale_in_threshold is not None:
        SCALING_CONFIG['scale_in_threshold'] = request.scale_in_threshold

    if request.check_interval is not None:
        SCALING_CONFIG['check_interval'] = request.check_interval

    if request.cooldown_period is not None:
        SCALING_CONFIG['cooldown_period'] = request.cooldown_period

    return {
        "message": "Auto-scaling configuration updated",
        "config": SCALING_CONFIG
    }


@app.get("/status")
def get_status():
    """Get current status of all resources"""
    resources = get_resources()
    asg_state = get_asg_state()
    asg = asg_state.get('app-asg', {})
    rpm = get_requests_per_minute()

    return {
        "security_groups": {
            "secure": resources.get('secure_sg_id'),
            "open": resources.get('open_sg_id')
        },
        "auto_scaling_group": {
            "name": "app-asg",
            "current_capacity": asg.get('DesiredCapacity'),
            "min_size": asg.get('MinSize'),
            "max_size": asg.get('MaxSize'),
            "instances": [inst.get('InstanceId') for inst in asg.get('Instances', [])],
            "last_scaling_time": asg.get('LastScalingTime')
        },
        "metrics": {
            "requests_per_minute": rpm,
            "scale_out_threshold": SCALING_CONFIG['scale_out_threshold'],
            "scale_in_threshold": SCALING_CONFIG['scale_in_threshold']
        }
    }


@app.get("/load-generator/{num_requests}")
async def generate_load(num_requests: int):
    """Generate artificial load to test auto-scaling"""
    if num_requests > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 requests allowed at once")

    for i in range(num_requests):
        request_timestamps.append(time.time())
        if i % 10 == 0:  # Add small delay every 10 requests
            await asyncio.sleep(0.01)

    rpm = get_requests_per_minute()
    return {
        "message": f"Generated {num_requests} requests",
        "current_rpm": rpm
    }


# Start background task for auto-scaling
@app.on_event("startup")
def startup_event():
    # Start the auto-scaling thread
    scaling_thread = threading.Thread(target=check_auto_scaling, daemon=True)
    scaling_thread.start()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)