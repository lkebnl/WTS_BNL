# -*- coding: utf-8 -*-
"""
File Name: cls_femb_config.py
Author: GSS
Mail: gao.hillhill@gmail.com
      lingyun.lke@gmail.com
Description:
Created Time: 3/20/2019 4:50:34 PM
Last modified: 05/11/2025 5:02:04 PM
"""
## =========================================
import numpy as np
import sys
import os
import string
import time
from datetime import datetime

import sys
import os

# Add the parent directory to sys.path so 'function' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import function.Rigol_DP800 as rigol
from function.report_path import get_test_subdir, init_report_session
from function.session_info import get_session_info
from function.cls_udp import CLS_UDP
from function.tcp_cfg import TCP_CFG
import struct
from function.raw_convertor import RAW_CONV
import matplotlib.pyplot as plt
import h5py
import datetime
import function.chkout as chkout_top
import function.rigol_dp832_ps as Power  # import power component
from function.ping_host import ping_host
import platform
import subprocess

## =========================================

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def print_header(msg):
    print("\033[35m" + "=" * 60 + "\033[0m")
    print("\033[35m" + msg + "\033[0m")
    print("\033[35m" + "=" * 60 + "\033[0m")

def print_pass(msg):
    print("\033[32m" + msg + "\033[0m")

def print_fail(msg):
    print("\033[31m" + msg + "\033[0m")

def print_warning(msg):
    print("\033[33m" + msg + "\033[0m")

def print_info(msg):
    print("\033[36m" + msg + "\033[0m")

# ============================================================================
# TROUBLESHOOTING MESSAGES
# ============================================================================
TROUBLESHOOT = {
    "wib_service_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: WIB SERVICE RESTART FAILED                   │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB not fully booted                                     │
│  • Network connection lost                                  │
│  • WIB firmware crashed                                     │
│  • Telnet service not responding                            │
│                                                             │
│  Actions:                                                   │
│  1. Check network cable connection to WIB                   │
│  2. Verify WIB IP address (192.168.121.1)                   │
│  3. Power cycle WIB and wait 30s for boot                   │
│  4. Check if WIB LEDs indicate normal operation             │
│  5. Try manual telnet: telnet 192.168.121.1                 │
└─────────────────────────────────────────────────────────────┘
""",
    "seoff_power_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: SEOFF MODE POWER CHECK FAILED                │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • FEMB not properly seated in slot                         │
│  • Power regulator failure on FEMB                          │
│  • Damaged FEMB connector pins                              │
│  • WIB slot power circuit issue                             │
│                                                             │
│  Actions:                                                   │
│  1. Power off and reseat FEMB in slot                       │
│  2. Inspect FEMB connector for bent/damaged pins            │
│  3. Check WIB slot connector for debris                     │
│  4. Try FEMB in different slot to isolate issue             │
│  5. Test with known-good FEMB if available                  │
└─────────────────────────────────────────────────────────────┘
""",
    "seon_power_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: SEON (SDC) MODE POWER CHECK FAILED           │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • SDC configuration not applied correctly                  │
│  • FEMB ASIC configuration error                            │
│  • Power rail instability in SDC mode                       │
│  • Communication error during configuration                 │
│                                                             │
│  Actions:                                                   │
│  1. Restart WIB service and retry                           │
│  2. Check FEMB configuration registers                      │
│  3. Verify power supply stability                           │
│  4. Reduce number of active channels if overloaded          │
│  5. Check for thermal issues on FEMB                        │
└─────────────────────────────────────────────────────────────┘
""",
    "diff_power_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: DIFF MODE POWER CHECK FAILED                 │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Differential mode configuration error                    │
│  • Increased power draw in DIFF mode                        │
│  • ASIC configuration not properly applied                  │
│  • Power supply current limit reached                       │
│                                                             │
│  Actions:                                                   │
│  1. Check PSU current limit settings                        │
│  2. Verify FEMB cooling is adequate                         │
│  3. Restart WIB service and retry configuration             │
│  4. Check for shorts on differential signal lines           │
│  5. Reduce operating voltage if within spec                 │
└─────────────────────────────────────────────────────────────┘
""",
    "udp_data_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: UDP DATA ACQUISITION FAILED                  │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • UDP stream not enabled                                   │
│  • Network congestion or packet loss                        │
│  • WIB UDP firmware issue                                   │
│  • Firewall blocking UDP packets                            │
│                                                             │
│  Actions:                                                   │
│  1. Verify UDP port is open (check firewall)                │
│  2. Check network cable and switch connection               │
│  3. Restart WIB service to reset UDP stream                 │
│  4. Verify WIB UDP firmware version                         │
│  5. Try reducing data rate if buffer overflow               │
└─────────────────────────────────────────────────────────────┘
""",
    "asic_readout_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: ASIC DATA READOUT FAILED                     │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • ASIC not responding to configuration                     │
│  • Data link between FEMB and WIB broken                    │
│  • Clock/sync signal issue                                  │
│  • ASIC power not stable                                    │
│                                                             │
│  Actions:                                                   │
│  1. Re-run FEMB configuration sequence                      │
│  2. Check FEMB power rails are within spec                  │
│  3. Verify clock and sync signals present                   │
│  4. Try reading from different ASIC                         │
│  5. Power cycle FEMB and reconfigure                        │
└─────────────────────────────────────────────────────────────┘
""",
    "tcp_link_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: TCP COMMUNICATION FAILED                     │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB not reachable on network                             │
│  • TCP port not responding                                  │
│  • WIB software crashed                                     │
│  • Network configuration error                              │
│                                                             │
│  Actions:                                                   │
│  1. Ping WIB: ping 192.168.121.1                            │
│  2. Check Ethernet cable connections                        │
│  3. Verify PC network interface configuration               │
│  4. Power cycle WIB if unresponsive                         │
│  5. Check WIB boot logs via serial console                  │
└─────────────────────────────────────────────────────────────┘
""",
    "femb_voltage_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: FEMB VOLTAGE OUT OF RANGE                    │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • FEMB power regulator failure                             │
│  • Excessive load on power rail                             │
│  • Poor connection at FEMB connector                        │
│  • WIB power distribution issue                             │
│                                                             │
│  Actions:                                                   │
│  1. Check FEMB connector seating                            │
│  2. Measure voltage at FEMB test points                     │
│  3. Verify WIB power supply is stable                       │
│  4. Check for shorts or damaged components                  │
│  5. Try FEMB in different slot                              │
└─────────────────────────────────────────────────────────────┘
""",
    "femb_current_high": """
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  WARNING: FEMB CURRENT TOO HIGH                          │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Short circuit on FEMB                                    │
│  • Component failure                                        │
│  • Excessive ASIC activity                                  │
│  • Thermal runaway condition                                │
│                                                             │
│  ⚠️  CAUTION: High current may indicate fault!               │
│                                                             │
│  Actions:                                                   │
│  1. Power off FEMB slot immediately                         │
│  2. Allow FEMB to cool down                                 │
│  3. Inspect for visible damage or burns                     │
│  4. Check for solder bridges or debris                      │
│  5. Do not retry without thorough inspection                │
└─────────────────────────────────────────────────────────────┘
"""
}

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================
def validate_power_mode(mode_name, pwr_en, detailed_checks):
    """Validate power mode test results and show troubleshooting if failed"""
    if pwr_en == 0:
        print_fail(f"  ✗ {mode_name} Mode Power Check FAILED")

        # Show which rails failed
        for rail in ["FE", "ADC", "CD", "BIAS"]:
            for check_type in ["voltage", "current"]:
                if not detailed_checks[rail][check_type]["pass"]:
                    error_msg = detailed_checks[rail][check_type].get("error", "Unknown error")
                    print_fail(f"    - {rail} {check_type}: {error_msg}")

        # Show appropriate troubleshoot message
        if mode_name == "SEOFF":
            print(TROUBLESHOOT["seoff_power_fail"])
        elif mode_name == "SEON":
            print(TROUBLESHOOT["seon_power_fail"])
        elif mode_name == "DIFF":
            print(TROUBLESHOOT["diff_power_fail"])

        return False
    else:
        print_pass(f"  ✓ {mode_name} Mode Power Check PASSED")
        return True

def validate_asic_data(chip_data, asic_num):
    """Validate ASIC data readout"""
    if chip_data is None:
        print_fail(f"  ✗ ASIC {asic_num} Data Readout FAILED")
        print(TROUBLESHOOT["asic_readout_fail"])
        return False
    else:
        print_pass(f"  ✓ ASIC {asic_num} Data Readout OK")
        return True

def retry_prompt(test_name):
    """Prompt user for retry, skip, or exit"""
    print_warning(f"\n  {test_name} has failures.")
    print("  Options:")
    print("    [R] Retry this test")
    print("    [S] Skip and continue")
    print("    [E] Exit test")

    while True:
        choice = input("  Enter choice (R/S/E): ").strip().upper()
        if choice in ['R', 'S', 'E']:
            return choice
        print("  Invalid choice. Please enter R, S, or E.")

# === Helper function for robust WIB service restart ===
def safe_restart_wib_service(max_retries=5, retry_delay=5):
    """
    Safely restart WIB service with automatic retry on failure.
    Raises RuntimeError if all retries are exhausted.
    """
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"\033[33mRetrying WIB service restart (attempt {attempt + 1}/{max_retries})...\033[0m")
            time.sleep(retry_delay)

        success = initial.restart_wib_service()
        if success:
            return True

        print_fail(f"WIB service restart attempt {attempt + 1} failed")

    # All retries exhausted - show troubleshoot and raise error
    print(TROUBLESHOOT["wib_service_fail"])
    raise RuntimeError("WIB service restart failed after all retries - connection refused")

##  === 01 power start =====================







# print("\033[35m" + "A_RT03_01 : Power Rail" + "\033[0m")

# Initialize timing dictionary
timing_dict = {}
test_start_time = time.time()
t1 = time.time()

psu = rigol.RigolDP800()
psu.safe_power_off()
time.sleep(0.1)
psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
time.sleep(5)  # Reduced from 10s to 5s - power stabilization
v1, c1 = psu.measure(1)
v2, c2 = psu.measure(2)
time.sleep(0.5)  # Reduced from 1s to 0.5s
print(c1)
print(c2)

time.sleep(15)  # Reduced from 20s to 15s - wait for boot

print("Power is acquired, Please start")
timing_dict["01_Power_Startup"] = time.time() - t1

## =========================================
t1 = time.time()
time.sleep(1)
##  === 02 internet connection =====================
ping_host(ip_address="192.168.121.1", count=4)
ping_host(ip_address="192.168.121.2", count=4)
timing_dict["02_Network_Check"] = time.time() - t1
# WIB_IP = input("link with 192.168.121.1 (y/n)")
time.sleep(1)

# putty = input("link with putty (y/n)")

## ========= Initialize WIB Service =========
t1 = time.time()
print("\033[35m" + "Initializing WIB service..." + "\033[0m")
import temp as initial
print("\033[32m" + "WIB service ready" + "\033[0m")
timing_dict["03_WIB_Init"] = time.time() - t1

## =========================================
t1 = time.time()
tcp = TCP_CFG()
udp = CLS_UDP()
conv = RAW_CONV()
now = datetime.datetime.now()
# === Setup report subdirectory using centralized report_path module ===
target_file_path = get_test_subdir("Test0402_FEMB_Slot2_Pulse")
rootdir = target_file_path
print(f"Report directory: {target_file_path}")

## ========== WIB monitor ADC ================
monitor01 = tcp.wib_mon_adc_read()
print(monitor01)
## =========================================
result_dict = {}
result_dict["datetime"] = now
result_dict["rootdir"] = rootdir
result_dict["error_log"] = []  # Initialize error log
result_dict["detailed_checks"] = {}  # Initialize detailed check results
timing_dict["04_TCP_UDP_Setup"] = time.time() - t1
ver = tcp.wib_ver()
if (ver[1] == 0x100):
    print("TCP link built.")  # 04 TCP/IP communication confirm
result_dict["WIB_TCP_FW_ver"] = ver[1]
longcable = False
if longcable:
    print("Long cable is in use...")
    tcp.tcp_poke(addr=0x08, data=longcable)
    if (tcp.tcp_peek(addr=0x08) == longcable):
        pass
    else:
        print("Configuration for long cable is error, please check, exit anyway.")
        input("hit any button and then 'Enter' to exit")
        exit()
else:
    print("Short cable is in use...")
    tcp.tcp_poke(addr=0x08, data=longcable)
    if tcp.tcp_peek(addr=0x08) == longcable:
        pass
    else:
        print("Configuration for short cable is error, please check, exit anyway.")
        input("hit any button and then 'Enter' to exit")
        exit()
udpver = udp.read_reg_wib(reg=0x100)
if (udpver == 0x1A5):  # 05 UDP communication Confirm
    print("UDP link built.")
result_dict["WIB_UDP_FW_ver"] = udpver

print("Initial experiment start...")

tcp.tcp_poke(addr=0x16, data=0x01)
tcp.tcp_peek(addr=0x16)
# ## ==========BREAK_FOR_DEBUG================
time.sleep(1)
# print("Break02")
# Break = input("Pass02 (y/n)")
## =========================================
tcp.tcp_poke(addr=0x16, data=0x00)
tcp.tcp_peek(addr=0x16)
## ==========BREAK_FOR_DEBUG================
time.sleep(1)
# print("Break03")
# Break = input("Pass03 (y/n)")
## =========================================

for fembi in [2]:
    print(fembi)
    femb = int(fembi)
    if femb == 0:
        tcp.link_cs = 0
    elif femb == 1:
        tcp.link_cs = 2
    elif femb == 2:
        tcp.link_cs = 4
    elif femb == 3:
        tcp.link_cs = 6
    femb_sn, env, toytpc, save_dir, tester, note = chkout_top.FEMB_CHKOUT_Input(SN = femb, rootdir=rootdir)
    result_dict["FEMB_SN"] = femb_sn
    result_dict["Env"] = env
    result_dict["Cd"] = toytpc
    result_dict["save_dir"] = save_dir
    result_dict["Tester"] = tester
    result_dict["Note"] = note
    safe_restart_wib_service()
    tcp.reset_restart_counter()
    # Power On
    print("Turn on FEMB on WIB slot {}".format(femb))
    v_fe = 3
    v_adc = 3.5
    v_cd = 3
    v_bias = 5.0
    iref_fe = 0.42
    iref_adc = 1.6
    iref_cd = 0.2
    iref_bias = 0.05
    tcp.femb_pwr_set(femb=femb, pwr_on=0)
    time.sleep(1)
    tcp.femb_pwr_set(femb=femb, pwr_on=1, v_fe=v_fe, v_adc=v_adc, v_cd=v_cd)
    time.sleep(1)
    # input('debug01')

    # === SEOFF Power Mode Test ===
    t1 = time.time()
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("\033[36m" + "Starting SEOFF Mode Power Test" + "\033[0m")
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("Restarting WIB service for SEOFF test...")
    safe_restart_wib_service()
    tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
    time.sleep(1)  # Reduced from 2s to 1s

    print('SEOFF')
    tcp.set_fe_board(sts=1, snc=0, sg0=0, sg1=0, st0=1, st1=1, swdac=0, dac=0x0)
    tcp.femb_cfg()
    time.sleep(1)  # Reduced from 1s to 0.5s
    for i in range(3):  # Reduced from 5 to 3 measurements
        pwr_info = tcp.femb_pwr_rd(femb=femb)
        time.sleep(0.1)  # Reduced from 0.2s to 0.1s
    time.sleep(0.5)  # Reduced from 1s to 0.5s
    pwr_info = tcp.femb_pwr_rd(femb=femb)
    print(pwr_info)
    pwr_en, detailed_checks = chkout_top.pwr_chk(pwr_info, v_fe, v_adc, v_cd, v_bias, iref_fe, iref_adc, iref_cd, iref_bias)

    # Store detailed check results
    result_dict["detailed_checks"]["SEOFF"] = detailed_checks

    # Validate and log errors
    seoff_ok = validate_power_mode("SEOFF", pwr_en, detailed_checks)
    if pwr_en == 0:
        for rail in ["FE", "ADC", "CD", "BIAS"]:
            for check_type in ["voltage", "current"]:
                if not detailed_checks[rail][check_type]["pass"]:
                    result_dict["error_log"].append({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "phase": "SEOFF Mode Test",
                        "type": f"{rail} {check_type.upper()} Out of Range",
                        "description": detailed_checks[rail][check_type]["error"]
                    })
        print_warning("Continuing test to collect all data...")

    result_dict["power_vfe_ref"] = (v_fe, iref_fe)
    result_dict["power_vadc_ref"] = (v_adc, iref_adc)
    result_dict["power_vcd_ref"] = (v_cd, iref_cd)
    result_dict["power_bias_ref"] = (v_bias, iref_bias)
    result_dict["seoff_test_status"] = "PASS" if pwr_en == 1 else "FAIL"
    timing_dict["05_SEOFF_Test"] = time.time() - t1


    # === SEON (SDC) Mode Power Test ===
    t1 = time.time()
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("\033[36m" + "Starting SEON (SDC) Mode Power Test" + "\033[0m")
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("Restarting WIB service for SEON test...")
    safe_restart_wib_service()
    tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
    time.sleep(0.1)  # Reduced from 2s to 1s

    print('SEON')
    tcp.set_fe_board(sts=1, snc=0, sg0=0, sg1=0, st0=1, st1=1, sdf = 1, swdac=1, dac=0x0)
    tcp.femb_cfg_sdc()
    time.sleep(0.5)  # Reduced from 1s to 0.5s
    for i in range(3):  # Reduced from 5 to 3 measurements
        pwr_info = tcp.femb_pwr_rd(femb=femb)
        time.sleep(0.1)  # Reduced from 0.2s to 0.1s
    time.sleep(0.5)  # Reduced from 1s to 0.5s
    pwr_info_sdc = tcp.femb_pwr_rd(femb=femb)
    print(pwr_info)
    pwr_en, detailed_checks = chkout_top.pwr_chk(pwr_info, v_fe, v_adc, v_cd, v_bias, iref_fe, iref_adc, iref_cd, iref_bias)

    # Store detailed check results
    result_dict["detailed_checks"]["SEON"] = detailed_checks

    # Validate and log errors
    seon_ok = validate_power_mode("SEON", pwr_en, detailed_checks)
    if pwr_en == 0:
        for rail in ["FE", "ADC", "CD", "BIAS"]:
            for check_type in ["voltage", "current"]:
                if not detailed_checks[rail][check_type]["pass"]:
                    result_dict["error_log"].append({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "phase": "SEON (SDC) Mode Test",
                        "type": f"{rail} {check_type.upper()} Out of Range",
                        "description": detailed_checks[rail][check_type]["error"]
                    })
        print_warning("Continuing test to collect all data...")

    result_dict["power_vfe_ref_sdc"] = (v_fe, iref_fe)
    result_dict["power_vadc_ref_sdc"] = (v_adc, iref_adc)
    result_dict["power_vcd_ref_sdc"] = (v_cd, iref_cd)
    result_dict["power_bias_ref_sdc"] = (v_bias, iref_bias)
    result_dict["seon_test_status"] = "PASS" if pwr_en == 1 else "FAIL"
    timing_dict["06_SEON_Test"] = time.time() - t1

    # === DIFF Mode Test ===
    t1 = time.time()
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("\033[36m" + "Starting DIFF Mode Power Test" + "\033[0m")
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("Restarting WIB service for DIFF test...")
    safe_restart_wib_service()
    tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
    time.sleep(0.1)  # Reduced from 2s to 1s

    print('DIFF')
    tcp.set_fe_board(sts=1, snc=0, sg0=0, sg1=0, st0=1, st1=1, sdd = 1, swdac=1, dac=0x0)
    tcp.femb_cfg_diff()
    time.sleep(0.5)  # Reduced from 1s to 0.5s
    for i in range(3):  # Reduced from 5 to 3 measurements
        pwr_info = tcp.femb_pwr_rd(femb=femb)
        time.sleep(0.1)  # Reduced from 0.2s to 0.1s
    time.sleep(0.5)  # Reduced from 1s to 0.5s
    pwr_info_diff = tcp.femb_pwr_rd(femb=femb)
    print(pwr_info)
    pwr_en, detailed_checks = chkout_top.pwr_chk(pwr_info, v_fe, v_adc, v_cd, v_bias, iref_fe, iref_adc, iref_cd, iref_bias)

    # Store detailed check results
    result_dict["detailed_checks"]["DIFF"] = detailed_checks

    # Validate and log errors
    diff_ok = validate_power_mode("DIFF", pwr_en, detailed_checks)
    if pwr_en == 0:
        for rail in ["FE", "ADC", "CD", "BIAS"]:
            for check_type in ["voltage", "current"]:
                if not detailed_checks[rail][check_type]["pass"]:
                    result_dict["error_log"].append({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "phase": "DIFF Mode Test",
                        "type": f"{rail} {check_type.upper()} Out of Range",
                        "description": detailed_checks[rail][check_type]["error"]
                    })
        print_warning("Continuing test to collect all data...")

    result_dict["power_vfe_ref_diff"] = (v_fe, iref_fe)
    result_dict["power_vadc_ref_diff"] = (v_adc, iref_adc)
    result_dict["power_vcd_ref_diff"] = (v_cd, iref_cd)
    result_dict["power_bias_ref_diff"] = (v_bias, iref_bias)
    result_dict["diff_test_status"] = "PASS" if pwr_en == 1 else "FAIL"
    timing_dict["07_DIFF_Test"] = time.time() - t1



    # === Data Acquisition & Analysis ===
    t1 = time.time()
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("\033[36m" + "Starting Data Acquisition & Analysis" + "\033[0m")
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("Restarting WIB service for data acquisition...")
    safe_restart_wib_service()
    tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
    time.sleep(0.1)

    ##########1#####################################################################################
    # FEMB configuration: 14mV/fC, 200mV BL, 2.0us, single-ended, 500pA, ASICDAC=0x10, Cali_enable, SDC off,
    result_dict["FE_CFG"] = "14mV/fC, 900mV BL, 2.0us, SE_OFF, 500pA, ASIC_CAL, ASICDAC=0x10"
    result_dict["ADC_CFG0"] = "CMOS reference set to default, Auto Calibration, "
    result_dict["ADC_CFG1"] = "SE, SDC off, offset_binary_format, Auto Calibration, "
    result_dict["CD_FE_pulse"] = "500 samples/pulse, CD Addr0x06:0x30,0x07:0x00, 0x08:0x38, 0x09:0x80"

    print("Measure monitoring parameters")
    tcp.set_fe_board(sts=0, snc=0, sg0=0, sg1=0, st0=1, st1=1, swdac=0, dac=0x10)
    tcp.femb_cfg()
    # for asic in range(8):
    for asic in [0, 4]:
        safe_restart_wib_service()
        tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
        print("Measure ASIC {}".format(asic))
        tmp = tcp.femb_adc_mon_cs(femb_no=femb, adc_no=asic)
        result_dict["ADC{:02d}_SetRef".format(asic)] = tmp[1]
        result_dict["ADC{:02d}_MeasRef".format(asic)] = tmp[0]

    # # === Data Acquisition & Analysis ===
    # print("\033[36m" + "=" * 60 + "\033[0m")
    # print("\033[36m" + "Starting Data Acquisition & Analysis" + "\033[0m")
    # print("\033[36m" + "=" * 60 + "\033[0m")
    # print("Restarting WIB service for data acquisition...")
    # initial.restart_wib_service()
    # tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
    # time.sleep(2)
    # tcp.set_fe_board(sts=0, snc=0, sg0=0, sg1=0, st0=1, st1=1, swdac=0, dac=0x0)
    # tcp.femb_cfg()
    #
    # for asic in [0, 4]:
    #     tmp = tcp.femb_fe_mon_cs(femb_no=femb, ext_lemo=0, rst_fe=0, mon_type=2, mon_chip=asic)
    #     result_dict["Mon_LArASIC{:02d}_BGR".format(asic)] = tmp
    # for asic in [0, 4]:
    #     tmp = tcp.femb_fe_mon_cs(femb_no=femb, ext_lemo=0, rst_fe=0, mon_type=1, mon_chip=asic)
    #     result_dict["Mon_LArASIC{:02d}_Temperature".format(asic)] = tmp

    # === Data Acquisition & Analysis ===
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("\033[36m" + "Starting Data Acquisition & Analysis" + "\033[0m")
    print("\033[36m" + "=" * 60 + "\033[0m")
    print("Restarting WIB service for data acquisition...")
    safe_restart_wib_service()
    tcp.reset_restart_counter()  # Reset auto-restart attempts for this phase
    time.sleep(0.1)  # Reduced from 2s to 1s
    print("Start FEMB configuration: 14mV/fC, 900mV BL, 2.0us, single-ended, 500pA, ASICDAC=0x10, Cali_enable, SDC off")
    #   [sg0 = 0, sg1 = 0 => 14mV/fC]   [snc = 0 => 900mV baseline] [st0 = 1, st1 = 1 => 2 us] [sts = 1 => test capacitance enable]
    tcp.set_fe_reset()
    tcp.set_fe_board(sts=1, snc=0, sg0=0, sg1=0, st0=1, st1=1, swdac=1, dac=0x10)
    tcp.set_fe_sync()
    tcp.femb_cfg()
    time.sleep(5)
    # check channel response
    print("Check channel response")

    hdf_fp = save_dir + "rawdata.h5"
    result_dict["H5"] = hdf_fp

    udp.write_reg_wib_checked(2, 1)
    time.sleep(1)
    print("Enable UDP data stream")
    udp.write_reg_wib_checked(2, 1)
    time.sleep(1)
    ASICs = 8

    # to avoid potential cache data in PC
    asic = 0
    wib_asic = (((femb << 16) & 0x000F0000) + ((asic << 8) & 0xFF00))
    udp.write_reg_wib_checked(7, 0x80000000)
    udp.write_reg_wib_checked(7, wib_asic | 0x80000000)
    udp.write_reg_wib_checked(7, wib_asic)
    time.sleep(0.01)
    data = udp.get_rawdata_packets(val=1000)

    femb_data = []
    dset = [[] for i in range(128)]
    while True:
        if os.path.isfile(hdf_fp):
            os.remove(hdf_fp)
        with h5py.File(hdf_fp, "a") as f:
            for asic in range(ASICs):
                print("FEMB{} ASIC{} is selected".format(femb, asic))
                asic = asic & 0x0F
                wib_asic = (((femb << 16) & 0x000F0000) + ((asic << 8) & 0xFF00))
                udp.write_reg_wib_checked(7, 0x80000000)
                udp.write_reg_wib_checked(7, wib_asic | 0x80000000)
                udp.write_reg_wib_checked(7, wib_asic)
                time.sleep(0.01)
                val = 1000
                data = udp.get_rawdata_packets(val=val)
                chip_data = conv.raw_conv_feedloc(data)
                if chip_data is not None:
                    end_while = True
                    femb_data.append(chip_data)
                    for i in range(16):
                        dset[i] = f.create_dataset('CH{}'.format(asic * 16 + i), (len(chip_data[i]),), maxshape=(None,),
                                                   dtype='u2', chunks=True)
                        dset[i][:] = chip_data[i]
                    print_pass(f"    ✓ ASIC {asic} data acquired successfully")
                else:
                    end_while = False
                    print_fail(f"    ✗ ASIC {asic} data acquisition FAILED")
                    print(TROUBLESHOOT["asic_readout_fail"])
            print("Start data analysis...")
            ana = chkout_top.data_ana(femb_data)
            if end_while:
                break

    print("Measure power consumption...")
    pwr_info = tcp.femb_pwr_rd(femb=femb)
    result_dict["power_vfe_ref"] = (v_fe, iref_fe)
    result_dict["power_vadc_ref"] = (v_adc, iref_adc)
    result_dict["power_vcd_ref"] = (v_cd, iref_cd,)
    result_dict["power_bias_ref"] = (v_bias, iref_bias)
    result_dict["power_vfe_meas"] = pwr_info[0]
    result_dict["power_vadc_meas"] = pwr_info[1]
    result_dict["power_vcd_meas"] = pwr_info[2]
    result_dict["power_bias_meas"] = pwr_info[4]

    result_dict["power_vfe_meas_sdc"] = pwr_info_sdc[0]
    result_dict["power_vadc_meas_sdc"] = pwr_info_sdc[1]
    result_dict["power_vcd_meas_sdc"] = pwr_info_sdc[2]
    result_dict["power_bias_meas_sdc"] = pwr_info_sdc[4]

    result_dict["power_vfe_meas_diff"] = pwr_info_diff[0]
    result_dict["power_vadc_meas_diff"] = pwr_info_diff[1]
    result_dict["power_vcd_meas_diff"] = pwr_info_diff[2]
    result_dict["power_bias_meas_diff"] = pwr_info_diff[4]

    fn = chkout_top.FEMB_PLOT(ana[0], ana[1], ana[2], ana[3], ana[4], ana[5], save_dir)
    result_dict["response.png"] = fn
    result_dict["data_acq_status"] = "PASS" if end_while else "FAIL"
    timing_dict["08_Data_Acquisition"] = time.time() - t1

    # Add timing information to result_dict
    result_dict["timing_dict"] = timing_dict
    result_dict["total_test_time"] = time.time() - test_start_time

    # Generate HTML report
    chkout_top.generate_report(result_dict)

    # Export detailed data to CSV
    try:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from function.csv_export import export_test0401_to_csv
        csv_path = export_test0401_to_csv(result_dict)
        print(f"\033[32mCSV report exported to: {csv_path}\033[0m")
    except Exception as e:
        print(f"\033[33mWarning: Could not export CSV: {e}\033[0m")

    print("Turn FEMB off")
    tcp.femb_pwr_set(femb=femb, pwr_on=0)

    # Display timing summary
    print("\n" + "="*60)
    print("\033[32m" + "TIMING SUMMARY" + "\033[0m")
    print("="*60)
    total_time = result_dict["total_test_time"]
    for phase, duration in timing_dict.items():
        percentage = (duration / total_time * 100) if total_time > 0 else 0
        print(f"{phase:30s}: {duration:6.2f}s ({percentage:5.1f}%)")
    print("-"*60)
    print(f"{'TOTAL TEST TIME':30s}: {total_time:6.2f}s")
    print("="*60)

    print("Test is done...")
    print("Report is saved at {}".format(result_dict["save_dir"]))

    # Set report path for final report integration
    import file.report_dict as rp_dict
    # Extract folder name from save_dir and create relative path
    folder_name = os.path.basename(result_dict["save_dir"].rstrip('/'))
    rp_dict.set_report_path('item043', folder_name + '/result.html')

print("Turn Power Supply off")
time.sleep(0.5)
psu.safe_power_off()
psu.close()

# Close Telnet connection if exists
print("Cleaning up Telnet connection...")
try:
    import temp as initial
    if hasattr(initial, 'disconnect'):
        initial.disconnect()
except:
    pass

print("Test completed successfully!")
#
