# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
import sys
import os
# import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# from function.rigol_dp832_ps import RIGOL_PS_CTL
from function.ping_host import ping_host
from datetime import datetime
import subprocess

import file.report_dict as rp_dict
import time
import path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import function.Rigol_DP800 as rigol
from function.report_path import get_test_subdir, init_report_session
from function.session_info import get_session_info

# ============================================================
# TROUBLESHOOT HELPER FUNCTIONS
# ============================================================

def print_header(msg):
    """Print header with purple color"""
    print("\033[35m" + "=" * 60 + "\033[0m")
    print("\033[35m" + msg + "\033[0m")
    print("\033[35m" + "=" * 60 + "\033[0m")

def print_pass(msg):
    """Print pass message with green color"""
    print("\033[32m" + msg + "\033[0m")

def print_fail(msg):
    """Print fail message with red color"""
    print("\033[31m" + msg + "\033[0m")

def print_warning(msg):
    """Print warning message with yellow color"""
    print("\033[33m" + msg + "\033[0m")

def print_info(msg):
    """Print info message with cyan color"""
    print("\033[36m" + msg + "\033[0m")

# ============================================================
# TROUBLESHOOT MESSAGES
# ============================================================

TROUBLESHOOT = {
    "psu_voltage_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: POWER SUPPLY VOLTAGE OUT OF RANGE            │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • PSU not properly connected                               │
│  • PSU output disabled                                      │
│  • Load exceeds PSU capacity                                │
│  • Faulty power cable                                       │
│                                                             │
│  Actions:                                                   │
│  1. Check Rigol DP800 front panel for output status         │
│  2. Verify power cables are securely connected              │
│  3. Check for shorts on WIB power input                     │
│  4. Verify PSU voltage/current settings                     │
│  5. Try power cycling the PSU                               │
└─────────────────────────────────────────────────────────────┘
""",
    "psu_current_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: POWER SUPPLY CURRENT ABNORMAL                │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB not drawing expected current (too low)               │
│  • Short circuit on WIB (too high)                          │
│  • WIB not fully initialized                                │
│  • Component failure on WIB                                 │
│                                                             │
│  CAUTION: High current may indicate fault!                  │
│                                                             │
│  Actions:                                                   │
│  1. If current too low: check WIB power connection          │
│  2. If current too high: power off immediately              │
│  3. Inspect WIB for visible damage                          │
│  4. Check for debris or shorts on connectors                │
│  5. Verify WIB boot status via serial console               │
└─────────────────────────────────────────────────────────────┘
""",
    "vivado_exec_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: VIVADO EXECUTION FAILED                      │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Vivado not installed or path incorrect                   │
│  • License server not available                             │
│  • TCL script file not found                                │
│  • Insufficient system resources                            │
│                                                             │
│  Actions:                                                   │
│  1. Verify Vivado path in path.xilinx_path                  │
│  2. Check Vivado license status                             │
│  3. Verify TCL script exists in file/ directory             │
│  4. Check available disk space and memory                   │
│  5. Try running Vivado manually to verify installation      │
└─────────────────────────────────────────────────────────────┘
""",
    "tcl_script_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: TCL SCRIPT EXECUTION ERROR                   │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • JTAG connection to FPGA lost                             │
│  • IBERT core not found in design                           │
│  • Hardware target not accessible                           │
│  • Script syntax error                                      │
│                                                             │
│  Actions:                                                   │
│  1. Check JTAG cable connection to WIB                      │
│  2. Verify FPGA is programmed with IBERT bitstream          │
│  3. Open Vivado Hardware Manager to check connection        │
│  4. Review TCL script for errors                            │
│  5. Check stderr output for specific error messages         │
└─────────────────────────────────────────────────────────────┘
""",
    "ber_parse_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: BER RESULTS PARSING FAILED                   │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • IBERT test did not complete                              │
│  • Unexpected output format from Vivado                     │
│  • MGT channels not configured correctly                    │
│  • Link not established on GTX transceivers                 │
│                                                             │
│  Actions:                                                   │
│  1. Check Vivado stdout for IBERT status messages           │
│  2. Verify MGT_X0Y4 and MGT_X0Y5 are configured             │
│  3. Ensure loopback or valid link is established            │
│  4. Increase IBERT test duration if needed                  │
│  5. Check TCL script output format matches parser           │
└─────────────────────────────────────────────────────────────┘
""",
    "x0y4_error_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: X0Y4 CHANNEL BIT ERRORS DETECTED             │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Signal integrity issue on MGT X0Y4                       │
│  • Incorrect TX/RX equalization settings                    │
│  • Clock quality or jitter issue                            │
│  • Physical layer problem (cable, connector)                │
│                                                             │
│  Channel: MGT_X0Y4 (GTX Transceiver)                        │
│                                                             │
│  Actions:                                                   │
│  1. Check eye scan plot for X0Y4 - look for closed eye      │
│  2. Verify TX and RX connections for X0Y4                   │
│  3. Adjust TX pre/post emphasis settings                    │
│  4. Check reference clock quality                           │
│  5. Inspect PCB traces and connectors for X0Y4              │
└─────────────────────────────────────────────────────────────┘
""",
    "x0y5_error_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: X0Y5 CHANNEL BIT ERRORS DETECTED             │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Signal integrity issue on MGT X0Y5                       │
│  • Incorrect TX/RX equalization settings                    │
│  • Clock quality or jitter issue                            │
│  • Physical layer problem (cable, connector)                │
│                                                             │
│  Channel: MGT_X0Y5 (GTX Transceiver)                        │
│                                                             │
│  Actions:                                                   │
│  1. Check eye scan plot for X0Y5 - look for closed eye      │
│  2. Verify TX and RX connections for X0Y5                   │
│  3. Adjust TX pre/post emphasis settings                    │
│  4. Check reference clock quality                           │
│  5. Inspect PCB traces and connectors for X0Y5              │
└─────────────────────────────────────────────────────────────┘
""",
    "eye_scan_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: EYE SCAN DATA NOT AVAILABLE                  │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Eye scan TCL script failed                               │
│  • CSV output files not generated                           │
│  • Insufficient test time for eye scan                      │
│  • IBERT eye scan feature not enabled                       │
│                                                             │
│  Expected Files: scan00.csv (X0Y4), scan01.csv (X0Y5)       │
│                                                             │
│  Actions:                                                   │
│  1. Check if scan00.csv and scan01.csv exist                │
│  2. Verify eyeScan.tcl script executed successfully         │
│  3. Check Vivado output for eye scan errors                 │
│  4. Ensure IBERT core supports eye scan feature             │
│  5. Try running eye scan manually in Vivado GUI             │
└─────────────────────────────────────────────────────────────┘
""",
    "plot_gen_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: EYE SCAN PLOT GENERATION FAILED              │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • CSV file format incorrect or corrupted                   │
│  • Missing matplotlib or numpy libraries                    │
│  • Insufficient data in CSV file                            │
│  • Output directory write permission issue                  │
│                                                             │
│  Actions:                                                   │
│  1. Verify CSV file has expected data format                │
│  2. Check Python dependencies (pandas, matplotlib, numpy)   │
│  3. Verify output directory exists and is writable          │
│  4. Check CSV file row/column counts                        │
│  5. Try opening CSV manually to verify contents             │
└─────────────────────────────────────────────────────────────┘
"""
}

# ============================================================
# VALIDATION FUNCTIONS
# ============================================================

def validate_power_supply(v1, c1, v2, c2, result_dict=None):
    """Validate power supply voltage and current readings"""
    errors = []

    # Check voltage ranges (11.0V - 13.0V expected for 12V supply)
    v1_ok = 11.0 <= v1 <= 13.0
    v2_ok = 11.0 <= v2 <= 13.0

    # Check combined current range (1.1A - 1.9A for Ch1+Ch2 total)
    total_current = c1 + c2
    total_ok = 1.1 <= total_current <= 1.9

    if not v1_ok:
        errors.append(f"Ch1 Voltage {v1:.3f}V out of range (11.0-13.0V)")
        print_fail(f"  ✗ Ch1 Voltage FAIL: {v1:.3f}V (expected 11.0-13.0V)")
        print_warning(TROUBLESHOOT["psu_voltage_fail"])
    else:
        print_pass(f"  ✓ Ch1 Voltage PASS: {v1:.3f}V")

    if not v2_ok:
        errors.append(f"Ch2 Voltage {v2:.3f}V out of range (11.0-13.0V)")
        print_fail(f"  ✗ Ch2 Voltage FAIL: {v2:.3f}V (expected 11.0-13.0V)")
        print_warning(TROUBLESHOOT["psu_voltage_fail"])
    else:
        print_pass(f"  ✓ Ch2 Voltage PASS: {v2:.3f}V")

    if not total_ok:
        errors.append(f"Total Current {total_current:.3f}A out of range (1.1-1.9A) [Ch1: {c1:.3f}A, Ch2: {c2:.3f}A]")
        print_fail(f"  ✗ Total Current FAIL: {total_current:.3f}A (Ch1: {c1:.3f}A + Ch2: {c2:.3f}A, expected 1.1-1.9A)")
        print_warning(TROUBLESHOOT["psu_current_fail"])
    else:
        print_pass(f"  ✓ Total Current PASS: {total_current:.3f}A (Ch1: {c1:.3f}A + Ch2: {c2:.3f}A)")

    if result_dict is not None and errors:
        if "error_log" not in result_dict:
            result_dict["error_log"] = []
        result_dict["error_log"].extend(errors)

    return len(errors) == 0

def validate_vivado_execution(process, script_name, result_dict=None):
    """Validate Vivado script execution"""
    if process.returncode != 0:
        print_fail(f"  ✗ Vivado script '{script_name}' FAILED (return code: {process.returncode})")
        if process.stderr:
            print_fail(f"    Error: {process.stderr[:200]}...")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"Vivado script {script_name} failed")
        return False
    else:
        print_pass(f"  ✓ Vivado script '{script_name}' completed successfully")
        return True

def validate_ber_parsing(log07_ibert, channel, result_dict=None):
    """Validate BER results were parsed for a channel"""
    ber_key = f"{channel}_Total_BER"
    error_key = f"{channel}_Total_ERROR_count"
    bit_key = f"{channel}_Total_BIT_count"

    missing = []
    if ber_key not in log07_ibert:
        missing.append("Total_BER")
    if error_key not in log07_ibert:
        missing.append("Total_ERROR_count")
    if bit_key not in log07_ibert:
        missing.append("Total_BIT_count")

    if missing:
        print_fail(f"  ✗ {channel} BER parsing FAILED - missing: {', '.join(missing)}")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"{channel} BER data not parsed")
        return False
    else:
        print_pass(f"  ✓ {channel} BER data parsed successfully")
        print_info(f"      BER: {log07_ibert[ber_key]}")
        print_info(f"      ERROR_count: {log07_ibert[error_key]}")
        print_info(f"      BIT_count: {log07_ibert[bit_key]}")
        return True

def validate_channel_errors(error_count, channel, result_dict=None):
    """Validate channel has zero errors"""
    if error_count == 0:
        print_pass(f"  ✓ {channel} ERROR_count = 0 (PASS)")
        return True
    else:
        print_fail(f"  ✗ {channel} ERROR_count = {error_count} (FAIL - expected 0)")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"{channel} has {error_count} bit errors")
        return False

def validate_eye_scan_file(filepath, channel, result_dict=None):
    """Validate eye scan CSV file exists"""
    if os.path.exists(filepath):
        file_size = os.path.getsize(filepath)
        print_pass(f"  ✓ {channel} eye scan file found ({file_size} bytes)")
        return True
    else:
        print_fail(f"  ✗ {channel} eye scan file NOT FOUND: {filepath}")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"{channel} eye scan file missing")
        return False

# ============================================================
# MAIN TEST
# ============================================================

print_header("A_RT07: IBERT (Integrated Bit Error Ratio Test)")

# Start time for test duration
t1 = time.time()

# Result dictionary for error logging
result_dict = {"error_log": []}

# Test tracking
tests_passed = 0
tests_failed = 0
test_failures = []

print_header("Power Supply Initialization")
psu = rigol.RigolDP800()

print_info("  Initializing Power Supply...")
psu.safe_power_off()
time.sleep(0.5)
print_info("  Turning WIB power ON...")
psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
time.sleep(10)
v1, c1 = psu.measure(1)
v2, c2 = psu.measure(2)  # Fixed: was psu.measure(1)
print_info(f"  WIB Power - Ch1: {v1:.3f}V {c1:.3f}A, Ch2: {v2:.3f}V {c2:.3f}A")

# Validate power supply
print_info("\n  Validating Power Supply...")
psu_ok = validate_power_supply(v1, c1, v2, c2, result_dict)
if psu_ok:
    tests_passed += 1
else:
    tests_failed += 1
    test_failures.append("Power Supply")

time.sleep(1) # wait for boot

project_dir = "/home/dune/Documents/DUNE_WIB_QC_Script"
vivado_path = path.xilinx_path
print(vivado_path)

# === Run IBERT Initialization TCL Script ===
print_header("IBERT Initialization")
print_info(f"  Vivado path: {vivado_path}")
print_info("  Running IBERT initialization TCL script...")

command = [vivado_path, "-mode", "batch", "-source", "./file/Test07_vivado_tcl_command.tcl"]
process = subprocess.run(command, capture_output=True, text=True, cwd=project_dir)

# Validate Vivado execution
ibert_init_ok = validate_vivado_execution(process, "Test07_vivado_tcl_command.tcl", result_dict)
if ibert_init_ok:
    tests_passed += 1
else:
    tests_failed += 1
    test_failures.append("IBERT Initialization")
    print_warning(TROUBLESHOOT["vivado_exec_fail"])

if process.stderr and "ERROR" in process.stderr:
    print_warning(TROUBLESHOOT["tcl_script_fail"])

# === Wait for BER accumulation ===
print_header("IBERT BER Test Running")
print_info("  Waiting 1000 seconds for BER accumulation...")
print_info("  (This allows sufficient bit counting for accurate BER measurement)")
time.sleep(1000)

# === Run BER Measurement TCL Script ===
print_header("BER Measurement")
print_info("  Running BER measurement TCL script...")

command = [vivado_path, "-mode", "batch", "-source", "file/tcl_02.tcl"]
process = subprocess.run(command, capture_output=True, text=True, cwd=project_dir)

# Validate BER measurement script
ber_script_ok = validate_vivado_execution(process, "tcl_02.tcl", result_dict)
if ber_script_ok:
    tests_passed += 1
else:
    tests_failed += 1
    test_failures.append("BER Measurement Script")
    print_warning(TROUBLESHOOT["tcl_script_fail"])

# === Parse BER Results ===
print_header("BER Results Parsing")
print_info("  Parsing Vivado output for BER data...")

log_text = process.stdout
for line in log_text.splitlines():
    line = line.strip()
    # Match X0Y4 channel (using MGT_X0Y4/RX pattern which is consistent)
    if 'MGT_X0Y4/RX Total_BER:' in line:
        rp_dict.log07_ibert["X0Y4_Total_BER"] = line.split("Total_BER:")[-1].strip()
    elif 'MGT_X0Y4/RX Total_ERROR_count:' in line:
        rp_dict.log07_ibert['X0Y4_Total_ERROR_count'] = line.split("Total_ERROR_count:")[-1].strip()
    elif 'MGT_X0Y4/RX Total_BIT_count:' in line:
        rp_dict.log07_ibert["X0Y4_Total_BIT_count"] = line.split("Total_BIT_count:")[-1].strip()
    # Match X0Y5 channel
    elif 'MGT_X0Y5/RX Total_BER:' in line:
        rp_dict.log07_ibert['X0Y5_Total_BER'] = line.split("Total_BER:")[-1].strip()
    elif 'MGT_X0Y5/RX Total_ERROR_count:' in line:
        rp_dict.log07_ibert["X0Y5_Total_ERROR_count"] = line.split("Total_ERROR_count:")[-1].strip()
    elif 'MGT_X0Y5/RX Total_BIT_count:' in line:
        rp_dict.log07_ibert['X0Y5_Total_BIT_count'] = line.split("Total_BIT_count:")[-1].strip()

# Validate BER parsing for both channels
x0y4_parse_ok = validate_ber_parsing(rp_dict.log07_ibert, "X0Y4", result_dict)
x0y5_parse_ok = validate_ber_parsing(rp_dict.log07_ibert, "X0Y5", result_dict)

if not x0y4_parse_ok or not x0y5_parse_ok:
    print_warning(TROUBLESHOOT["ber_parse_fail"])
    tests_failed += 1
    test_failures.append("BER Parsing")
else:
    tests_passed += 1
# === Evaluate Test Result: Total_ERROR_count should be 0 ===
print_header("Error Count Evaluation")
print_info("  Evaluating bit error counts...")

# Error counts are in hexadecimal format (e.g., 000000000000)
x0y4_error_str = rp_dict.log07_ibert.get('X0Y4_Total_ERROR_count', '-1')
x0y5_error_str = rp_dict.log07_ibert.get('X0Y5_Total_ERROR_count', '-1')

# === Setup Output Directory BEFORE Eye Scan ===
# Create output directory first so TCL can write directly to it
output_dir = get_test_subdir("Test07_IBERT")
print_info(f"  Eye scan output directory: {output_dir}")

# === Run Eye Scan TCL Script ===
print_header("Eye Scan Acquisition")
print_info("  Running eye scan TCL script...")
time.sleep(10)

# Pass output directory to TCL via environment variable
env = os.environ.copy()
env['EYE_SCAN_OUTPUT_DIR'] = output_dir

command = [vivado_path, "-mode", "batch", "-source", "file/eyeScan.tcl"]
process = subprocess.run(command, capture_output=True, text=True, cwd=project_dir, env=env)

eye_scan_ok = validate_vivado_execution(process, "eyeScan.tcl", result_dict)
if eye_scan_ok:
    tests_passed += 1
else:
    tests_failed += 1
    test_failures.append("Eye Scan Script")

# Parse hex values (handle both hex string and decimal)
try:
    x0y4_error_count = int(x0y4_error_str, 16)  # Parse as hexadecimal
except ValueError:
    x0y4_error_count = int(x0y4_error_str) if x0y4_error_str != '-1' else -1

try:
    x0y5_error_count = int(x0y5_error_str, 16)  # Parse as hexadecimal
except ValueError:
    x0y5_error_count = int(x0y5_error_str) if x0y5_error_str != '-1' else -1

# Validate channel error counts
print_info("\n  Channel Error Count Results:")
x0y4_ok = validate_channel_errors(x0y4_error_count, "X0Y4", result_dict)
x0y5_ok = validate_channel_errors(x0y5_error_count, "X0Y5", result_dict)

if not x0y4_ok:
    tests_failed += 1
    test_failures.append("X0Y4 Error Count")
    print_warning(TROUBLESHOOT["x0y4_error_fail"])
else:
    tests_passed += 1

if not x0y5_ok:
    tests_failed += 1
    test_failures.append("X0Y5 Error Count")
    print_warning(TROUBLESHOOT["x0y5_error_fail"])
else:
    tests_passed += 1

# Determine pass/fail for each channel with result and decision
x0y4_decision = "PASS" if x0y4_error_count == 0 else "FAIL"
x0y5_decision = "PASS" if x0y5_error_count == 0 else "FAIL"

rp_dict.log07_ibert['X0Y4_Total_ERROR_count_Decision'] = x0y4_decision
rp_dict.log07_ibert['X0Y5_Total_ERROR_count_Decision'] = x0y5_decision

# Overall test status: PASS only if both channels have 0 errors
if x0y4_error_count == 0 and x0y5_error_count == 0:
    rp_dict.log07_ibert['Overall_Test_Status'] = "PASS"
else:
    rp_dict.log07_ibert['Overall_Test_Status'] = "FAIL"

# === Test Summary ===
print_header("Test07 IBERT Summary")
print_info(f"  Tests Passed: {tests_passed}")
print_info(f"  Tests Failed: {tests_failed}")

if test_failures:
    print_fail(f"\n  Failed Tests ({len(test_failures)}):")
    for fail in test_failures:
        print_fail(f"    - {fail}")

# Final status
if x0y4_error_count == 0 and x0y5_error_count == 0:
    print_pass("\n  IBERT Test PASSED: Total_ERROR_count is 0 for both channels")
    print_pass("  Overall Status: PASS")
else:
    print_fail(f"\n  IBERT Test FAILED:")
    print_fail(f"    X0Y4 ERROR_count = {x0y4_error_count} ({x0y4_decision})")
    print_fail(f"    X0Y5 ERROR_count = {x0y5_error_count} ({x0y5_decision})")
    print_fail("  Overall Status: FAIL")

# Log errors if any
if result_dict.get("error_log"):
    print_warning(f"\n  Total errors logged: {len(result_dict['error_log'])}")

t2 = time.time()
test_duration = round(t2 - t1, 2)
print_info(f"\n  Test Duration: {test_duration} seconds")

print_info("\n  Turning Power Supply OFF...")
time.sleep(0.5)
psu.safe_power_off()
psu.close()
# fm_ps.off([1, 2, 3])




# === Output directory already created before eye scan ===
base_dir = os.path.dirname(os.path.abspath(__file__))

# Get the main report directory (same level as Final_Report)
from function.report_path import get_report_dir
main_report_dir = get_report_dir()

print(f"\n{'=' * 60}")
print(f"Eye Scan Files Directory: {output_dir}")
print(f"Main Report Directory: {main_report_dir}")
print(f"{'=' * 60}\n")

# Store output directory in rp_dict for reference
rp_dict.log07_ibert['Output_Directory'] = output_dir

# Validate eye scan CSV files (written directly by TCL script)
print_header("Eye Scan File Validation")
scan00_path = os.path.join(output_dir, "scan00_X0Y4.csv")
scan01_path = os.path.join(output_dir, "scan01_X0Y5.csv")

print_info("  Checking eye scan CSV files generated by TCL...")
scan00_exists = validate_eye_scan_file(scan00_path, "X0Y4", result_dict)
scan01_exists = validate_eye_scan_file(scan01_path, "X0Y5", result_dict)

if not scan00_exists or not scan01_exists:
    print_warning(TROUBLESHOOT["eye_scan_fail"])

# === Generate Eye Scan Plots ===
print_header("Eye Scan Plot Generation")

# === X0Y4 Eye Scan Plot ===
print_info("  Generating X0Y4 eye scan plot...")
try:
    # Use CSV file directly from output directory (written by TCL script)
    eye_data = pd.read_csv(scan00_path, skiprows=22, nrows=30, header=None, usecols=range(1, 10))
    eye_matrix = eye_data.apply(pd.to_numeric, errors='coerce').dropna(how='any').values

    # Replace zeros to avoid log scale crash
    eye_matrix[eye_matrix == 0] = 1e-12

    # Plot with vivid color layering and log scale
    plt.figure(figsize=(10, 6))
    img = plt.imshow(
        eye_matrix,
        aspect='auto',
        cmap='jet',
        origin='lower',
        norm=LogNorm(vmin=1e-10, vmax=1e-0)
    )

    # Add colorbar with log ticks
    cbar = plt.colorbar(img)
    cbar.set_label('Bit Error Rate (log scale)')
    cbar.set_ticks([1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1e-0])
    cbar.ax.set_yticklabels(['1e-10', '1e-9', '1e-8', '1e-7', '1e-6', '1e-5', '1e-4', '1e-3', '1e-2', '1e-1', '1e-0'])

    # Add labels and layout
    plt.title('Eye Scan for X0Y4 (Log BER Heatmap)')
    plt.xlabel('Horizontal Offset (UI)')
    plt.ylabel('Vertical Offset (Codes)')
    plt.tight_layout()
    target_file_path1 = os.path.join(output_dir, "eye_scan_X0Y4.png")
    plt.savefig(target_file_path1, dpi=300, bbox_inches='tight')
    print_pass(f"  ✓ Saved: eye_scan_X0Y4.png")
except Exception as e:
    print_fail(f"  ✗ X0Y4 plot generation FAILED: {e}")
    print_warning(TROUBLESHOOT["plot_gen_fail"])
    target_file_path1 = None

# === X0Y5 Eye Scan Plot ===
print_info("  Generating X0Y5 eye scan plot...")
try:
    # Use CSV file directly from output directory (written by TCL script)
    eye_data = pd.read_csv(scan01_path, skiprows=22, nrows=30, header=None, usecols=range(1, 10))
    eye_matrix = eye_data.apply(pd.to_numeric, errors='coerce').dropna(how='any').values

    # Replace zeros to avoid log scale crash
    eye_matrix[eye_matrix == 0] = 1e-12

    # Plot with vivid color layering and log scale
    plt.figure(figsize=(10, 6))
    img = plt.imshow(
        eye_matrix,
        aspect='auto',
        cmap='jet',
        origin='lower',
        norm=LogNorm(vmin=1e-10, vmax=1e-0)
    )

    # Add colorbar with log ticks
    cbar = plt.colorbar(img)
    cbar.set_label('Bit Error Rate (log scale)')
    cbar.set_ticks([1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1e-0])
    cbar.ax.set_yticklabels(['1e-10', '1e-9', '1e-8', '1e-7', '1e-6', '1e-5', '1e-4', '1e-3', '1e-2', '1e-1', '1e-0'])

    # Add labels and layout
    plt.title('Eye Scan for X0Y5 (Log BER Heatmap)')
    plt.xlabel('Horizontal Offset (UI)')
    plt.ylabel('Vertical Offset (Codes)')
    plt.tight_layout()
    target_file_path2 = os.path.join(output_dir, "eye_scan_X0Y5.png")
    plt.savefig(target_file_path2, dpi=300, bbox_inches='tight')
    print_pass(f"  ✓ Saved: eye_scan_X0Y5.png")
except Exception as e:
    print_fail(f"  ✗ X0Y5 plot generation FAILED: {e}")
    print_warning(TROUBLESHOOT["plot_gen_fail"])
    target_file_path2 = None

# === Setup HTML report path at main report level with _P/_F suffix ===
# Determine suffix based on overall test result
overall_result = rp_dict.log07_ibert.get('Overall_Test_Status', 'FAIL')
result_suffix = "_P" if overall_result == "PASS" else "_F"
target_file_path = os.path.join(main_report_dir, f"Test07_IBERT_report{result_suffix}.html")
print(f"HTML Report: {target_file_path}")
print(f"Test Result: {overall_result} (suffix: {result_suffix})")

# Print rp_dict.log07_ibert contents for verification
# print("\n" + "=" * 60)
# print("rp_dict.log07_ibert contents:")
# print("=" * 60)
# for key, value in rp_dict.log07_ibert.items():
#     print(f"  {key}: {value}")
# print("=" * 60 + "\n")

# Build table rows with status highlighting
rows = ""
if len(rp_dict.log07_ibert) == 0:
    rows = '<tr><td colspan="2" style="text-align: center; color: red;">No data captured - rp_dict.log07_ibert is empty</td></tr>\n'
else:
    for key, value in rp_dict.log07_ibert.items():
        # Add color styling for Decision and Status fields
        if 'Decision' in key or 'Status' in key:
            if value == "PASS":
                value_html = f'<span style="color: green; font-weight: bold;">{value}</span>'
            else:
                value_html = f'<span style="color: red; font-weight: bold;">{value}</span>'
        elif 'ERROR_count_Result' in key:
            # Highlight error count results - red if not 0, green if 0
            try:
                if int(value) != 0:
                    value_html = f'<span style="color: red; font-weight: bold;">{value}</span>'
                else:
                    value_html = f'<span style="color: green; font-weight: bold;">{value}</span>'
            except:
                value_html = str(value)
        else:
            value_html = str(value)
        rows += f"<tr><td>{key}</td><td>{value}</td></tr>\n"

# Determine overall status for header styling
overall_status = rp_dict.log07_ibert.get('Overall_Test_Status', 'UNKNOWN')
status_color = "#28a745" if overall_status == "PASS" else "#dc3545"
status_bg = "#d4edda" if overall_status == "PASS" else "#f8d7da"

# HTML content with styling
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WIB_07 WIB IBERT</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f9f9f9;
            color: #333;
        }}
        h2 {{
            text-align: center;
            color: #444;
        }}
        .status-banner {{
            text-align: center;
            padding: 15px;
            margin: 20px auto;
            width: 60%;
            border-radius: 8px;
            font-size: 1.2em;
            font-weight: bold;
        }}
        table {{
            width: 60%;
            margin: 20px auto;
            border-collapse: collapse;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px 15px;
            text-align: left;
        }}
        th {{
            background-color: #f0f0f0;
            font-weight: bold;
            text-align: center;
        }}
        tr:nth-child(even) td {{
            background-color: #fafafa;
        }}
        .images {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 30px;
        }}
        .images img {{
            max-width: 48%;
            border-radius: 6px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.15);
        }}
    </style>
</head>
<body>
    <h2>WIB IBERT Report</h2>
    <div class="status-banner" style="background-color: {status_bg}; color: {status_color}; border: 2px solid {status_color};">
        Overall Test Status: {overall_status}
    </div>

    <h3 style="text-align: center; margin-top: 30px;">IBERT (Integrated Bit Error Ratio Tester) serial analyzer</h3>
    <table>
        <thead>
            <tr>
                <th>Item</th>
                <th>Value</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <h3 style="text-align: center; margin-top: 30px;">Eye Scan Results</h3>
    <div class="images">
        <img src="./Test07_IBERT/eye_scan_X0Y4.png" alt="Eye Scan X0Y4">
        <img src="./Test07_IBERT/eye_scan_X0Y5.png" alt="Eye Scan X0Y5">
    </div>
    <div class="footer">
        <p>Made by Lingyun Ke</p>
    </div>
</body>
</html>
"""

# Always create new file (overwrite if exists)
with open(target_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML report saved to {target_file_path}")

# === Export test data to CSV ===
csv_file_path = os.path.join(output_dir, "IBERT_test_results.csv")
try:
    with open(csv_file_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("Item,Value\n")
        for key, value in rp_dict.log07_ibert.items():
            csv_file.write(f"{key},{value}\n")
    print(f"CSV report saved to {csv_file_path}")
except Exception as e:
    print(f"Warning: Could not save CSV: {e}")

# === Print Output Directory Summary ===
print("\n" + "=" * 60)
print("TEST 07 IBERT - OUTPUT FILES SUMMARY")
print("=" * 60)
print(f"Output Directory: {output_dir}")
print("-" * 60)
print("Files generated:")
for f in os.listdir(output_dir):
    file_path = os.path.join(output_dir, f)
    file_size = os.path.getsize(file_path)
    print(f"  - {f} ({file_size} bytes)")
print("=" * 60)
print(f"\nAll files saved to: {output_dir}")
print("Ready for network drive copy.")

