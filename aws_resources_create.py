# setup.py
import boto3
import json


def create_resources():
    # LocalStack endpoint
    endpoint_url = "http://localhost:4566"

    # Initialize clients
    ec2 = boto3.client('ec2', endpoint_url=endpoint_url, region_name='us-east-1',
                       aws_access_key_id='test', aws_secret_access_key='test')
    autoscaling = boto3.client('autoscaling', endpoint_url=endpoint_url, region_name='us-east-1',
                               aws_access_key_id='test', aws_secret_access_key='test')

    # Create security groups
    secure_sg = ec2.create_security_group(
        GroupName='secure-sg',
        Description='Allows only HTTP traffic'
    )
    secure_sg_id = secure_sg['GroupId']

    # Allow only HTTP
    ec2.authorize_security_group_ingress(
        GroupId=secure_sg_id,
        IpPermissions=[{'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}]
    )

    open_sg = ec2.create_security_group(
        GroupName='open-sg',
        Description='Allows all traffic'
    )
    open_sg_id = open_sg['GroupId']

    # Allow all traffic
    ec2.authorize_security_group_ingress(
        GroupId=open_sg_id,
        IpPermissions=[{'IpProtocol': '-1', 'FromPort': -1, 'ToPort': -1, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}]
    )

    # Create launch template with secure SG
    response = ec2.create_launch_template(
        LaunchTemplateName='app-template',
        VersionDescription='Initial version',
        LaunchTemplateData={
            'ImageId': 'ami-12345678',
            'InstanceType': 't2.micro',
            'SecurityGroupIds': [secure_sg_id]
        }
    )

    # Create auto-scaling group
    autoscaling.create_auto_scaling_group(
        AutoScalingGroupName='app-asg',
        MinSize=1,
        MaxSize=5,
        DesiredCapacity=2,
        LaunchTemplate={
            'LaunchTemplateId': response['LaunchTemplate']['LaunchTemplateId'],
            'Version': '$Latest'
        },
        AvailabilityZones=['us-east-1a']
    )

    # Create scaling policies
    autoscaling.put_scaling_policy(
        AutoScalingGroupName='app-asg',
        PolicyName='scale-out',
        PolicyType='SimpleScaling',
        AdjustmentType='ChangeInCapacity',
        ScalingAdjustment=1
    )

    autoscaling.put_scaling_policy(
        AutoScalingGroupName='app-asg',
        PolicyName='scale-in',
        PolicyType='SimpleScaling',
        AdjustmentType='ChangeInCapacity',
        ScalingAdjustment=-1
    )

    # Save resource IDs for the app
    resources = {
        'secure_sg_id': secure_sg_id,
        'open_sg_id': open_sg_id
    }

    with open('resources.json', 'w') as f:
        json.dump(resources, f)

    return resources


if __name__ == "__main__":
    create_resources()