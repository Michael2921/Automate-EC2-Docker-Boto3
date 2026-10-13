import boto3
import time
import paramiko
import requests
import schedule

ec2 = boto3.client("ec2")


file_location = 'C:\\Users\\user\\.ssh\\id_rsa.pub'

with open(file_location, 'r') as file:
    public_key_contents = file.read()

import_public_key = ec2.import_key_pair(
    KeyName='PublicKeyforEC2',
    PublicKeyMaterial=public_key_contents
)

print("Key pair is created")


create_security_group = ec2.authorize_security_group_ingress(
    GroupId='sg-0066ecb57ae1d22a3',
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [
                {
                    'Description': 'Security group created with Boto for inbound SSH access',
                    'CidrIp': '12.34.56.78/32'

                }
            ]
        },

{
            'IpProtocol': 'tcp',
            'FromPort': 8080,
            'ToPort': 8080,
            'IpRanges': [
                {
                    'Description': 'Security group created with Boto for inbound HTTP access',
                    'CidrIp': '12.34.56.78/32'

                }
            ]
        }
    ]
)

print("Security group is created")




#run_instances defaults instance type to a t3.small, but should be specified in run_instances

created_instances = ec2.run_instances(
        ImageId = "ami-0d27e0fb3bac4d724",
        MinCount = 1,
        MaxCount = 1,
        KeyName='PublicKeyforEC2',
        InstanceType='t3.small'
)

print("Instance is created, waiting for public ip")
time.sleep(15)


# default vpc also assigns a public IP to instance


describe_instances = ec2.describe_instances()

instance_id = created_instances['Instances'][0]['InstanceId']

describe_instances_by_id = ec2.describe_instances(InstanceIds=[instance_id])

instance = describe_instances_by_id['Reservations'][0]['Instances'][0]

public_ipv4 = instance.get('PublicIpAddress')


print(f"Instance ID is {instance_id}")
print(f"Public IP address is {public_ipv4}")


def ssh_access():

    ssh = paramiko.SSHClient()

    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(public_ipv4, username='ec2-user', key_filename='C:\\Users\\user\\.ssh\\id_rsa')

    return ssh



def install_docker():

    ssh = ssh_access()

    print("Connecting to the server")

    print("Executing docker install commands...")

    commands_install_docker = [
        'sudo dnf install -y docker',
        'sudo systemctl start docker',
        'sudo usermod -aG docker ec2-user', # docker group is automatically created on install
        # docker group permissions will not be active in the existing SSH session. Close session and start a new one.



    ]

    for cmd in commands_install_docker:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()

        print(f"Command: {cmd}")
        print(stdout.read().decode())
        print(stderr.read().decode())

    ssh.close()



def install_and_run_nginx():

    ssh = ssh_access()

    print("Connecting to the server")

    print("Executing install and run nginx commands...")

    commands_install_nginx = [
        'docker run -p 8080:80 -d nginx:1.30.5',
        'docker ps'
    ]

    for cmd in commands_install_nginx:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.channel.recv_exit_status()

        print(f"Command: {cmd}")
        print(stdout.read().decode())
        print(stderr.read().decode())

    ssh.close()


def check_instance_status():

    ec2_status = ec2.describe_instance_status(InstanceIds=instance_id)
    status = ec2_status['InstanceStatuses'][0]['InstanceState']['Name']
    return status


while True:
    print("Checking status of instance...")
    if check_instance_status() == "running":
        print("Instance is running")
        install_docker()
        install_and_run_nginx()
        break
    time.sleep(5)


def restart_container():

    ssh = ssh_access()

    stdin, stdout, stderr = ssh.exec_command("docker ps -q | head -n 1") # dynamically get the container ID
    container_id = stdout.read().decode().strip()

    stdin, stdout, stderr = ssh.exec_command(f"docker restart {container_id}") # starts container with dynamically retrieved container ID
    print(stdout.read().decode())
    print(stderr.read().decode())

    ssh.close()


check_counter = 0

# every 5 seconds, it checks for the status, for a total of 5 times (25 seconds) if 5 checks fail, it restarts the application.


def monitor_application():

    global check_counter

    response = requests.get(f'http://{public_ipv4}:8080')

    print("Monitoring application health...")
    if response.status_code != 200:
        print("Site is not reachable")
        check_counter += 1
        print(f"failed counter is {check_counter}")
        if check_counter == 5:
            print(f"failed counter is {check_counter}, restarting the container")
            restart_container()
            check_counter = 0


schedule.every(5).seconds.do(monitor_application)


while True:
    schedule.run_pending()










