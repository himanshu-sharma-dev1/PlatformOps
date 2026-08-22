'''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : scripts.py
* Description       : Functions related to check the system info
*
* Revision History  :
* Date                          Author                          Comments
* ---------------------------------------------------------------------------------------------------------------------
* 1-march-25                  YashKumar                        Created.
*
*********************************************************************************************************************'''



import os
import psutil
import GPUtil
import distro
import platform
import subprocess
import json

distribution_name = "None"
distribution_version = "None"
specs_dict = {}

# Get OS info
os_info = platform.uname()
if os_info.system == 'Linux':
    distribution_name = distro.name()
    distribution_version = distro.version()
elif os_info.system == 'Windows':
    distribution_name = os_info.system
    distribution_version = os_info.version

# Get CPU information
num_logical_processors = psutil.cpu_count(logical=True)

# Get memory information
memory = psutil.virtual_memory()
total_memory_gb = memory.total / (1024 ** 3)
free_memory_gb = memory.available / (1024 ** 3)

# Get disk information
disk = psutil.disk_usage('/')
total_disk_space_gb = disk.total / (1024 ** 3)
free_disk_space_gb = disk.free / (1024 ** 3)

# Get GPU information
#gpus = GPUtil.getGPUs()

# Check if Docker is installed
docker_installed = os.system("docker > /dev/null 2>&1") == 0

def check_nvidia_container_toolkit():
    try:
        result = subprocess.run(["dpkg", "-l", "nvidia-container-toolkit"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        result = subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "nvidia" in result.stdout.lower():
            return True
    except FileNotFoundError:
        pass
    return False

def check_nvidia_compute_capability():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            return None
        compute_cap = result.stdout.strip().split('\n')[1]
        return compute_cap
    except FileNotFoundError:
        return None

nvidia_container_toolkit_installed = check_nvidia_container_toolkit()
compute_cap = check_nvidia_compute_capability()
#gpu_info = []

#for gpu in gpus:
#    gpu_info.append({
#        "Name": gpu.name,
#        "Driver Version": gpu.driver,
#        "Cuda Compute Capability": float(compute_cap) if compute_cap else None,
#        "Total Memory": int(gpu.memoryTotal / 1024),
#        "Free Memory": int(gpu.memoryFree / 1024)
#    })

specs_dict["CPU Info"] = {
    "vCPUs": num_logical_processors,
    #"Total RAM (GBs)": int(total_memory_gb),
    "RAM (GBs)": int(free_memory_gb),
    #"Total Storage (GBs)": int(total_disk_space_gb),
    "Storage (GBs)": int(free_disk_space_gb)
}
#specs_dict["GPU Info"] = gpu_info
specs_dict["SW Info"] = {
    "OS Type": os_info.system,
    "Distribution Name": distribution_name,
    "Distribution Version": distribution_version,
    "Docker Installed": "Yes" if docker_installed else "No",
    "NVIDIA Container Toolkit Installed": "Yes" if nvidia_container_toolkit_installed else "No"
}

# ✅ Print as JSON
print(json.dumps(specs_dict))  # Ensure output is valid JSON