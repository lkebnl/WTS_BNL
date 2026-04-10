#!/usr/bin/env python3
# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
"""
Test0801: SSH Passwordless Login Verification
─────────────────────────────────────────────
Flow per attempt (up to MAX_RETRIES):
  1. Power OFF WIB
  2. Power ON WIB, wait for boot
  3. Test passwordless SSH (BatchMode — no password prompt)
  4. If login OK → PASS, done
  5. If login requires password → run ssh-copy-id, test again
  6. If still failing → next attempt
After MAX_RETRIES failures: send email alert.
Results saved to test08_combined_data.json for merged report.
"""

import subprocess
import os
import sys
import csv
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import function.Rigol_DP800 as rigol
import GUI.send_email as send_email
from function.report_path import get_report_dir

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.realpath(__file__))
SSH_SCRIPT  = os.path.join(SCRIPT_DIR, "copy_ssh_key.sh")

REMOTES     = ["192.168.121.123"]
USER        = "root"
PASSWORD    = "fpga"
BOOT_WAIT   = 30        # seconds after power-on before testing SSH
MAX_RETRIES = 3

SENDER_EMAIL    = "bnlr216@gmail.com"
SENDER_PASSWORD = "vvef tosp minf wwhf"

WIB_INFO_PATH = os.path.join(os.path.dirname(__file__), '..', 'file', 'wib_info.csv')

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _read_wib_info(key):
    try:
        with open(WIB_INFO_PATH, mode='r', newline='', encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) == 2 and row[0].strip() == key:
                    return row[1].strip()
    except Exception:
        pass
    return None


def ssh_test(ip):
    """Return True if passwordless SSH login succeeds (no password prompt)."""
    result = subprocess.run(
        ["ssh",
         "-o", "BatchMode=yes",
         "-o", "ConnectTimeout=10",
         "-o", "StrictHostKeyChecking=no",
         f"{USER}@{ip}",
         "echo OK"],
        capture_output=True, text=True
    )
    ok = result.returncode == 0 and "OK" in result.stdout
    if ok:
        print(f"\033[0;32m[SSH] ✓ Passwordless login OK ({ip})\033[0m")
    else:
        print(f"\033[0;31m[SSH] ✗ Login failed or requires password ({ip})\033[0m")
        if result.stderr.strip():
            print(f"      stderr: {result.stderr.strip()}")
    return ok



def run_ssh_setup_script(ip):
    """Run copy_ssh_key.sh, answering the password prompt automatically via pexpect."""
    if not os.path.isfile(SSH_SCRIPT):
        print(f"[ERROR] copy_ssh_key.sh not found: {SSH_SCRIPT}")
        return False
    os.chmod(SSH_SCRIPT, 0o755)
    remote = f"{USER}@{ip}"
    print(f"[INFO] Running {SSH_SCRIPT} {remote} ...")
    try:
        import pexpect
        child = pexpect.spawn(f"{SSH_SCRIPT} {remote}", encoding='utf-8', timeout=60)
        child.logfile_read = sys.stdout   # echo script output to terminal
        # The script may ask for password one or more times (ssh-copy-id prompts per SSH call)
        while True:
            idx = child.expect(['[Pp]assword:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
            if idx == 0:
                child.sendline(PASSWORD)
            else:
                break
        child.close()
        ok = child.exitstatus == 0
    except ImportError:
        print("[WARN] pexpect not installed — running script without auto-password (may hang)")
        result = subprocess.run([SSH_SCRIPT, remote], text=True)
        ok = result.returncode == 0
    if ok:
        print("[INFO] copy_ssh_key.sh completed successfully")
    else:
        print("[WARN] copy_ssh_key.sh failed")
    return ok


def send_failure_email(ip, attempts, tester_email):
    """Send email alert when all retries are exhausted."""
    if not tester_email or '@' not in tester_email:
        print("[WARN] No valid tester email — skipping alert.")
        return
    wib_id = _read_wib_info('WIB_ID') or 'Unknown'
    subject = f"[WIB QC ALERT] Test0801 SSH setup FAILED — WIB {wib_id}"
    body = f"""\
WIB QC — Test0801 SSH Passwordless Login FAILED
================================================
WIB ID   : {wib_id}
Target   : {USER}@{ip}
Attempts : {attempts} / {MAX_RETRIES}
Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Passwordless SSH login could not be established after {attempts} attempts.
Please check:
  - WIB network connection (192.168.121.x)
  - WIB SD card and root filesystem integrity
  - SSH authorized_keys on the WIB

Manual check: ssh root@{ip}
If a password is prompted, the key was not installed.

---
Automated message from WIB QC Test0801
Made by Lingyun Ke
"""
    try:
        send_email.send_email(SENDER_EMAIL, SENDER_PASSWORD, [tester_email], subject, body)
        print(f"[INFO] Alert email sent to {tester_email}")
    except Exception as e:
        print(f"[WARN] Could not send alert email: {e}")


def save_test08_result(status, details):
    """Append Test0801 result to test08_combined_data.json in the report dir."""
    try:
        report_dir = get_report_dir()
        data_path = os.path.join(report_dir, 'test08_combined_data.json')
        data = {}
        if os.path.exists(data_path):
            with open(data_path) as f:
                data = json.load(f)
        data['test0801'] = {
            'status': status,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **details
        }
        with open(data_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[INFO] Test0801 result saved to {data_path}")
    except Exception as e:
        print(f"[WARN] Could not save test08 combined data: {e}")


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    tester_email = _read_wib_info('tester_email') or ''
    wib_id = _read_wib_info('WIB_ID') or 'Unknown'

    print(f"\n{'='*56}")
    print("  Test0801: SSH Passwordless Login Verification")
    print(f"  WIB ID: {wib_id}")
    print(f"{'='*56}")

    psu = rigol.RigolDP800()
    overall_success = True   # True until any remote fails
    remote_results = {}      # ip → 'pass' | 'fail'

    for ip in REMOTES:
        print(f"\n{'─'*56}")
        print(f"  Target: {USER}@{ip}")
        print(f"{'─'*56}")

        passed = False

        for attempt in range(1, MAX_RETRIES + 1):
            print(f"\n[Attempt {attempt}/{MAX_RETRIES}]")

            # ── Power cycle ──────────────────────────────────
            print("[INFO] Powering OFF WIB...")
            psu.safe_power_off()
            time.sleep(3)

            print("[INFO] Powering ON WIB...")
            psu.set_channel(1, 12.0, 3.0, on=True)
            psu.set_channel(2, 12.0, 3.0, on=True)
            print(f"[INFO] Waiting {BOOT_WAIT}s for WIB to boot...")
            for remaining in range(BOOT_WAIT, 0, -1):
                print(f"\r  Boot countdown: {remaining:2d}s ", end="", flush=True)
                time.sleep(1)
            print()

            # ── Copy SSH key first ────────────────────────────
            print("[INFO] Running copy_ssh_key.sh ...")
            run_ssh_setup_script(ip)

            # ── Then test passwordless SSH ────────────────────
            print("[INFO] Testing passwordless SSH login...")
            if ssh_test(ip):
                passed = True
                break

            # Still failing
            if attempt < MAX_RETRIES:
                print(f"[INFO] Attempt {attempt} failed. Retrying...")
            else:
                print(f"[FAIL] All {MAX_RETRIES} attempts failed for {ip}.")
                send_failure_email(ip, attempt, tester_email)

        remote_results[ip] = 'pass' if passed else 'fail'
        if not passed:
            overall_success = False

    # ── Power OFF ────────────────────────────────────────────
    print("\n[INFO] Powering OFF WIB...")
    psu.safe_power_off()
    psu.close()

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'='*56}")
    print("  Test0801 Summary")
    print(f"{'='*56}")
    ok_hosts   = [ip for ip, r in remote_results.items() if r == 'pass']
    fail_hosts = [ip for ip, r in remote_results.items() if r == 'fail']
    for ip in ok_hosts:
        print(f"\033[0;32m  [PASS] {USER}@{ip}\033[0m")
    for ip in fail_hosts:
        print(f"\033[0;31m  [FAIL] {USER}@{ip}\033[0m")

    final_status = "PASS" if overall_success else "FAIL"
    color = "\033[0;32m" if overall_success else "\033[0;31m"
    print(f"\n{color}  Overall: {final_status}\033[0m")

    # ── Save to combined data file ────────────────────────────
    save_test08_result(
        status=final_status,
        details={
            'remotes_success': ok_hosts,
            'remotes_failed':  fail_hosts,
            'max_retries':     MAX_RETRIES
        }
    )

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
