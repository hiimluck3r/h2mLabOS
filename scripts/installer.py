import os
import subprocess
import datetime
import time
from beaupy import confirm, prompt, select, select_multiple
from beaupy.spinners import *
from rich.console import Console

console = Console()

console.print("""[blue]
██╗  ██╗██╗██╗███╗   ███╗                
██║  ██║██║██║████╗ ████║                
███████║██║██║██╔████╔██║                
██╔══██║██║██║██║╚██╔╝██║                
██║  ██║██║██║██║ ╚═╝ ██║                
╚═╝  ╚═╝╚═╝╚═╝╚═╝     ╚═╝                
                                         
██╗      █████╗ ██████╗  ██████╗ ███████╗
██║     ██╔══██╗██╔══██╗██╔═══██╗██╔════╝
██║     ███████║██████╔╝██║   ██║███████╗
██║     ██╔══██║██╔══██╗██║   ██║╚════██║
███████╗██║  ██║██████╔╝╚██████╔╝███████║
╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚══════╝
--------
Created by @hiimluck3r
https://github.com/hiimluck3r/h2m[/blue]
""")

domains = []
console.print("*Username is used for managing nodes and for different services.")
user = input("Enter your username: ")
if confirm("\nDo you want to use a single domain?"):
    domains.append(input("Enter domain of the cluster: "))
else:
    domain_count = int(input("How many domains do you want to use? "))
    for i in range(domain_count):
        domains.append(input(f"Enter domain #{i}: "))
email = input("Enter your email: ")
console.print("""[red]
    ***
    This password is going to be used to access different nodes and to configure specific applications.
    ***
    [/red]""")
password = prompt("Enter your password: ", secure=True)

while True:
    if len(password) < 10:
        password = prompt("Weak password! Use 10 to 32 characters: ", secure=True)
    elif len(password) > 32:
        password = prompt("Too much! Use 10 to 32 characters: ", secure=True)
    else:
        break

print(f"\nUser: {user}")
print(f"Domains: {domains}")
print(f"E-mail: {email}")

confirmation = input("Proceed? (y/n): ")
if confirmation != "y":
    print("Aborting the process...")
    exit()

while True:
    console.print("""[yellow]
    ***
    Single-node: master and worker are on the same node
    Multi-node: master and worker have different nodes | [orange] Is being tested [/orange]
    ***[/yellow]
    """)
    cluster_mode = input("Will the k3s cluster be single-node or multi-node? (s/m): ")
    if cluster_mode in ["s", "m"]:
        break
    else:
        print('Use "s" for single-node or "m" for multi-node as an answer string.')

master_nodes = []
worker_nodes = []
singlenode = ""

if cluster_mode == "s":
    singlenode = input("Enter the IP of the cluster node: ")
else:
    while True:
        try:
            master_nodes_amount = int(input("How many master nodes do you want? Enter odd number: "))
            if (master_nodes_amount%2 == 0) or (master_nodes_amount <= 0):
                print(f"The amount of master nodes cannot equal to {master_nodes_amount}. Odd number of nodes is required for quorum.")
            else:
                for i in range(master_nodes_amount):
                    master_nodes.append(input(f"{i+1}. Enter the IP of master node: "))
                break
        except Exception as e:
            print(f"Exception found at the master node creation: {e}")
            exit()
    
    while True:
        try:
            worker_nodes_amount = int(input("How many worker nodes do you want: "))
            if (worker_nodes_amount <= 0):
                print(f"The amount of worker nodes cannot be equal to {worker_nodes_amount}.")
            else:
                for i in range(worker_nodes_amount):
                    worker_nodes.append(input(f"{i+1}. Enter the IP of worker node: "))
                break
        except Exception as e:
            print(f"Exception found at the worker node creation: {e}")
            exit()

cp_vip = "" #Control-plane Virtual IP
if len(master_nodes) >= 1:
    while True:
        cp_vip = input("Enter free IP that will be used for Control-Plane LoadBalancer. It must be different from the IPs you entered above: ")
        if cp_vip not in master_nodes:
            break

#Service LoadBalancer IP range
console.print("""[yellow]
    ***
    CIDR-based IP example: 192.168.0.10/29.
    /29 is subnet mask 255.255.255.248
    ***[/yellow]
""")
cidr_global = input("Enter CIDR-based IP range: ")

console.print("""[yellow]
    ***
    Example: eth0. You can check it with [red]ip addr[/red] on a virtual machine
    ***[/yellow]
""")
kube_vip_interface = input("Enter network inteface that KubeVip will bind to: ")

production_https = 'false'

if confirm("\nUse HTTPS? For HTTPS connection you will need CloudFlare API Token to solve DNS01 challenge."):
    cloudflare_token = prompt("""[yellow]
    ***
    DNS01 challenge creates temporary DNS-record to confirm than you are domain's owner.
    The only supported provider (at least for now) is CloudFlare.
    If you are using multiple domains, make sure all of them are proxied within single account accessible with the following API.             

    To create CloudFlare API token:
    1. Go to User Profile (My Profile)
    2. API Tokens -> Create API Token
    3. Configure the following permissions:
        [white]Zone - DNS - Edit
        Zone - Zone - Red[/white]
    4. Configure the following Zone resources:
        [white]Include - All Zones[/white]
    ***[/yellow]

Enter CloudFlare API token: 
""", secure=True)
    if confirm("\nUse production Let's encrypt server? (You can change it manually in group_vars/all/h2mconfig.yml):"):
        production_https = 'true'
else:
    cloudflare_token = ''

def get_domains(domains):
    result = ""
    for domain in domains:
        result+=f'   - {domain}\n'
    return result

newline = '\n'

console.print("""---
[red]Creating ansible-inventory...[/red]""")

with open("../inventory", "w") as inv_file:
    inv_file.write(f"""[leader]
{master_nodes[0] if len(master_nodes)!=0 else ""}

[quorum]
{newline.join(master_nodes[1::])}

[master:children]
leader
quorum

[cluster]
{singlenode}

[worker]
{newline.join(worker_nodes)}

[k3c:children]
master
cluster""")

with open('../config/littlelink_env.yml', 'r') as littlelink_file:
    littlelink_env = littlelink_file.read()

with open("/etc/timezone", 'r') as tz_file:
    timezone = tz_file.read()

with open("../config/apps_cfg.yml", 'r') as apps_file:
    apps_env = apps_file.read()

with open("../config/storage_cfg.yml", 'r') as storage_file:
    storage_cfg = storage_file.read()

with open("../group_vars/all/h2mcfg.yml", 'w') as sys_file:
    sys_file.write(f"""---
#Cluster config
https: {'true' if cloudflare_token!='' else 'false'}
production_https: {production_https}
kube_vip_leader_ip: {cp_vip} #Control-plane Virtual IP
cidr_global: {cidr_global} #CIDR-based kube-vip LoadBalancer IP range
domains:
{get_domains(domains)}
user: {user}
kube_vip_interface: {kube_vip_interface}
kube_vip_version: v0.6.4

#Storage config
{storage_cfg}

#Applications
TZ: {timezone}
{apps_env}

#LittleLink
{littlelink_env} {datetime.date.today().year}
""") #kube_vip_version 0.6.4 is stable

with open("../group_vars/all/vault.yml", 'w') as vault_file:
    vault_file.write(f"""---
email: {email}
password: {password}
cloudflare_token: {cloudflare_token}
""")

vault_encrypt = subprocess.call(["ansible-vault", "encrypt", "../group_vars/all/vault.yml"])

console.print("[red]Don't forget this password since it's the only way of decrypting secrets you provided before.[/red]")