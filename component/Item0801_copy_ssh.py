#!/usr/bin/env python3
# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
setup_all_remotes.py
Run copy_ssh_key.sh for all remote hosts
"""

import subprocess
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# could be remove or changed if no rigol power supply
# ===========
import function.Rigol_DP800 as rigol
# ===========

# -------------------------------
# Configuration
# -------------------------------
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SSH_SCRIPT = os.path.join(SCRIPT_DIR, "copy_ssh_key.sh")

REMOTES = [
    "192.168.121.123",
]

USER = "root"
PASSWORD = "fpga"

# -------------------------------
# Power ON
# -------------------------------
# could be remove or changed if no rigol power supply
# ===========
print("[INFO] Powering ON WIB...")
psu = rigol.RigolDP800()
psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
print("[INFO] Waiting for WIB to boot...")
time.sleep(30)
# ===========

# -------------------------------
# Check script exists
# -------------------------------
if not os.path.isfile(SSH_SCRIPT):
    print(f"[ERROR] copy_ssh_key.sh not found at: {SSH_SCRIPT}")
    rigol.RigolDP800.safe_power_off(psu)
    psu.close()
    exit(1)

os.chmod(SSH_SCRIPT, 0o755)

# Install sshpass if needed
subprocess.run(["sudo", "apt-get", "install", "-y", "sshpass"],
               capture_output=True)

# -------------------------------
# Add host to known_hosts
# -------------------------------
def add_known_host(ip):
    print(f"[INFO] Scanning host key for {ip}...")
    result = subprocess.run(
        ["ssh-keyscan", "-H", ip],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"[WARN] Could not scan host key for {ip}")
        return

    known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    os.makedirs(os.path.dirname(known_hosts), exist_ok=True)

    existing = ""
    if os.path.isfile(known_hosts):
        with open(known_hosts, "r") as f:
            existing = f.read()

    if ip not in existing:
        with open(known_hosts, "a") as f:
            f.write(result.stdout)
        print(f"[INFO] Added {ip} to known_hosts")
    else:
        print(f"[INFO] {ip} already in known_hosts")

# -------------------------------
# Copy key using sshpass
# -------------------------------
def copy_ssh_key(ip, user, password):
    remote = f"{user}@{ip}"
    pub_key = os.path.expanduser("~/.ssh/id_ed25519.pub")

    if not os.path.isfile(pub_key):
        print(f"[INFO] Generating SSH key...")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f",
             os.path.expanduser("~/.ssh/id_ed25519"), "-N", ""],
            check=True
        )

    print(f"[INFO] Copying key to {remote}...")
    result = subprocess.run(
        ["sshpass", "-p", password,
         "ssh-copy-id", "-i", pub_key,
         "-o", "StrictHostKeyChecking=no",
         remote],
        text=True
    )
    return result.returncode == 0

# -------------------------------
# Run for each remote
# -------------------------------
success = []
failed = []

for ip in REMOTES:
    remote = f"{USER}@{ip}"
    print(f"\n{'='*48}")
    print(f"  Setting up SSH for: {remote}")
    print(f"{'='*48}")

    add_known_host(ip)

    if copy_ssh_key(ip, USER, PASSWORD):
        success.append(remote)
        print(f"[INFO] Testing passwordless login...")
        test = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             remote, "echo OK"],
            capture_output=True, text=True
        )
        if test.returncode == 0:
            print(f"\033[0;32m[INFO] ✓ Passwordless SSH working\033[0m")
        else:
            print(f"\033[1;33m[WARN] Key copied but login test failed\033[0m")
    else:
        failed.append(remote)

# -------------------------------
# Summary
# -------------------------------
print(f"\n{'='*48}")
print("  SUMMARY")
print(f"{'='*48}")

for h in success:
    print(f"\033[0;32m[OK]   {h}\033[0m")

for h in failed:
    print(f"\033[0;31m[FAIL] {h}\033[0m")

# -------------------------------
# Power OFF
# -------------------------------
print("\n[INFO] Powering OFF WIB...")
# could be remove or changed if no rigol power supply
# ===========
rigol.RigolDP800.safe_power_off(psu)
psu.close()
# ===========