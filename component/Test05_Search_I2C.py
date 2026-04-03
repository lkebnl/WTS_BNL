# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
import socket
import time
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from function.rigol_dp832_ps import RIGOL_PS_CTL
import function.Rigol_DP800 as rigol
from function.csv_manager import WIB_QC_CSV_Manager
from function.report_path import get_report_path, init_report_session
from function.session_info import get_session_info, get_report_filename
from function.ping_host import ping_host
from datetime import datetime
from function.cls_udp import CLS_UDP
from function.tcp_cfg import TCP_CFG
from function.raw_convertor import RAW_CONV
import time
import file.report_dict as rp_dict
from datetime import datetime

SERVER_IP = "192.168.121.1"
PORT = 23  # Change if necessary (23 for Telnet, 22 for SSH)
USERNAME = "root"
PASSWORD = "root"
INITIAL_COMMAND = "i2cset -y 1 0x70 0xff 0xff"

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
    "connection_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: WIB CONNECTION FAILED                        │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB not powered on or not fully booted                   │
│  • Network cable disconnected                               │
│  • Incorrect IP address (expected 192.168.121.1)            │
│  • Telnet service not running on WIB                        │
│                                                             │
│  Actions:                                                   │
│  1. Check WIB power LED indicators                          │
│  2. Verify network cable connection                         │
│  3. Wait 30 seconds for WIB to fully boot                   │
│  4. Try: ping 192.168.121.1                                 │
│  5. Try: telnet 192.168.121.1 23                            │
└─────────────────────────────────────────────────────────────┘
""",
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
    "ping_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: WIB PING FAILED                              │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB not fully booted (need ~30s after power on)          │
│  • Network interface not configured                         │
│  • Ethernet cable issue                                     │
│  • IP address conflict on network                           │
│                                                             │
│  Actions:                                                   │
│  1. Wait additional 30 seconds and retry                    │
│  2. Check Ethernet link LEDs on WIB and switch              │
│  3. Verify PC network interface is on 192.168.121.x         │
│  4. Try different Ethernet cable                            │
│  5. Check WIB serial console for boot errors                │
└─────────────────────────────────────────────────────────────┘
""",
    "i2c_device_missing": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: I2C DEVICE NOT DETECTED                      │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • I2C bus multiplexer not configured correctly             │
│  • Device failure or not populated on board                 │
│  • I2C bus pull-up resistor issue                           │
│  • Clock/data line problem                                  │
│                                                             │
│  Actions:                                                   │
│  1. Check I2C multiplexer (TCA9546A) is responding          │
│  2. Verify device is soldered on the board                  │
│  3. Check for cold solder joints near device                │
│  4. Measure I2C bus pull-up voltage (~3.3V)                 │
│  5. Try slower I2C bus speed if available                   │
└─────────────────────────────────────────────────────────────┘
""",
    "tcp_poke_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: TCP POKE COMMAND FAILED                      │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB TCP server not responding                            │
│  • Network connection interrupted                           │
│  • WIB firmware issue                                       │
│  • Register address invalid                                 │
│                                                             │
│  Actions:                                                   │
│  1. Verify WIB is still reachable (ping test)               │
│  2. Restart WIB service if available                        │
│  3. Check TCP port connectivity                             │
│  4. Power cycle WIB and retry                               │
│  5. Check WIB firmware version compatibility                │
└─────────────────────────────────────────────────────────────┘
""",
    "i2c_command_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: I2C COMMAND EXECUTION FAILED                 │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • I2C bus busy or locked                                   │
│  • Device not responding to address                         │
│  • Timeout during I2C transaction                           │
│  • Linux I2C driver issue                                   │
│                                                             │
│  Actions:                                                   │
│  1. Reset I2C bus: i2cset -y <bus> 0x00 0x06                │
│  2. Check I2C bus with: i2cdetect -y <bus>                  │
│  3. Verify I2C device address is correct                    │
│  4. Reboot WIB to reset I2C controllers                     │
│  5. Check dmesg for I2C error messages                      │
└─────────────────────────────────────────────────────────────┘
""",
    "login_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: WIB LOGIN FAILED                             │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Incorrect username/password (expected root/root)         │
│  • WIB boot not complete                                    │
│  • Telnet service not started                               │
│  • Previous session still active                            │
│                                                             │
│  Actions:                                                   │
│  1. Verify credentials: username=root, password=root        │
│  2. Wait for WIB to fully boot (~30 seconds)                │
│  3. Try connecting via serial console                       │
│  4. Power cycle WIB to reset active sessions                │
│  5. Check if max login sessions reached                     │
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

    # Check current ranges (0.5A - 3.0A expected)
    c1_ok = 0.5 <= c1 <= 3.0
    c2_ok = 0.5 <= c2 <= 3.0

    if not v1_ok:
        errors.append(f"Ch1 Voltage {v1:.3f}V out of range (11.0-13.0V)")
        print_fail(f"  ✗ Ch1 Voltage FAIL: {v1:.3f}V (expected 11.0-13.0V)")
        print_warning(TROUBLESHOOT["psu_voltage_fail"])
    else:
        print_pass(f"  ✓ Ch1 Voltage PASS: {v1:.3f}V")

    if not c1_ok:
        errors.append(f"Ch1 Current {c1:.3f}A out of range (0.5-3.0A)")
        print_fail(f"  ✗ Ch1 Current FAIL: {c1:.3f}A (expected 0.5-3.0A)")
        print_warning(TROUBLESHOOT["psu_current_fail"])
    else:
        print_pass(f"  ✓ Ch1 Current PASS: {c1:.3f}A")

    if not v2_ok:
        errors.append(f"Ch2 Voltage {v2:.3f}V out of range (11.0-13.0V)")
        print_fail(f"  ✗ Ch2 Voltage FAIL: {v2:.3f}V (expected 11.0-13.0V)")
        print_warning(TROUBLESHOOT["psu_voltage_fail"])
    else:
        print_pass(f"  ✓ Ch2 Voltage PASS: {v2:.3f}V")

    if not c2_ok:
        errors.append(f"Ch2 Current {c2:.3f}A out of range (0.5-3.0A)")
        print_fail(f"  ✗ Ch2 Current FAIL: {c2:.3f}A (expected 0.5-3.0A)")
        print_warning(TROUBLESHOOT["psu_current_fail"])
    else:
        print_pass(f"  ✓ Ch2 Current PASS: {c2:.3f}A")

    if result_dict is not None and errors:
        if "error_log" not in result_dict:
            result_dict["error_log"] = []
        result_dict["error_log"].extend(errors)

    return len(errors) == 0

def validate_i2c_device(readback, device, address, result_dict=None):
    """Validate I2C device detection and show troubleshoot on failure"""
    if address.lower() in readback.lower():
        print_pass(f"    ✓ I2C Device {device} found at 0x{address}")
        return True
    else:
        print_fail(f"    ✗ I2C Device {device} NOT FOUND at 0x{address}")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"I2C device {device} not detected at 0x{address}")
        return False

def show_i2c_troubleshoot():
    """Display I2C troubleshooting message"""
    print_warning(TROUBLESHOOT["i2c_device_missing"])

def validate_connection(connection, result_dict=None):
    """Validate WIB connection"""
    if connection is None:
        print_fail("  ✗ WIB Connection FAILED")
        print_warning(TROUBLESHOOT["connection_fail"])
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append("Failed to connect to WIB via Telnet")
        return False
    else:
        print_pass("  ✓ WIB Connection ESTABLISHED")
        return True

def retry_prompt(test_name):
    """Prompt user for action on test failure"""
    print_warning(f"\n  Test '{test_name}' encountered issues.")
    print_info("  Options: [R]etry | [S]kip | [E]xit")
    while True:
        choice = input("  Enter choice (R/S/E): ").strip().upper()
        if choice in ['R', 'S', 'E']:
            return choice
        print_warning("  Invalid choice. Please enter R, S, or E.")

t1 = time.time()

def receive_response(sock):
    """ Helper function to receive data from the socket """
    time.sleep(1)  # Give the server time to respond
    response = sock.recv(4096).decode(errors='ignore')
    print(response)  # Print the response for debugging
    return response

def connect_to_server():
    """ Establishes connection to the Zynq server and logs in """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, PORT))
        print("Connected to server.")

        # Read initial login prompt
        receive_response(s)

        # Send username and read response
        s.sendall((USERNAME + "\n").encode())
        receive_response(s)

        # Send password and read response
        s.sendall((PASSWORD + "\n").encode())
        receive_response(s)

        # Ensure login completion
        s.sendall(b"\n")
        receive_response(s)

        print("Login successful.")
        return s  # Keep the socket open for further commands

    except Exception as e:
        print("Connection error:", e)
        return None

def send_command(sock, command):
    """ Sends a command to the server and receives the response """
    try:
        sock.sendall((command + "\n").encode())
        response = receive_response(sock)
        return response
    except Exception as e:
        print("Error sending command:", e)
        return None




print_header("A_RT05_01 : Search I2C")

# Result dictionary for error logging
result_dict = {"error_log": []}

t1 = time.time()
psu = rigol.RigolDP800()

print_info("  Initializing Power Supply...")
psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
time.sleep(10)
v1, c1 = psu.measure(1)
v2, c2 = psu.measure(2)
print_info(f"  WIB Power - Ch1: {v1:.3f}V {c1:.3f}A, Ch2: {v2:.3f}V {c2:.3f}A")

# Validate power supply
print_info("\n  Validating Power Supply...")
psu_ok = validate_power_supply(v1, c1, v2, c2, result_dict)

# Update CSV with WIB power measurements
if rp_dict.csv_manager:
    v1_status = "PASS" if 11.0 <= v1 <= 13.0 else "FAIL"
    c1_status = "PASS" if 0.5 <= c1 <= 3.0 else "FAIL"
    v2_status = "PASS" if 11.0 <= v2 <= 13.0 else "FAIL"
    c2_status = "PASS" if 0.5 <= c2 <= 3.0 else "FAIL"

    rp_dict.csv_manager.batch_update([
        {"item_id": "T05_00", "value": round(v1, 3), "status": v1_status},
        {"item_id": "T05_01", "value": round(c1, 3), "status": c1_status},
        {"item_id": "T05_02", "value": round(v2, 3), "status": v2_status},
        {"item_id": "T05_03", "value": round(c2, 3), "status": c2_status}
    ])

time.sleep(1)

print_info("\n  Waiting for WIB boot (27 seconds)...")
time.sleep(27) # wait for boot
print_info("  Pinging WIB...")
ping_host(ip_address="192.168.121.1", count=4)
ping_host(ip_address="192.168.121.2", count=4)
time.sleep(1)
import component.temp as initial
initial
tcp = TCP_CFG()
udp = CLS_UDP()
conv = RAW_CONV()
now = datetime.now()

# Connect to WIB
print_info("\n  Connecting to WIB via Telnet...")
connection = connect_to_server()

# Validate connection
if not validate_connection(connection, result_dict):
    print_fail("  Cannot proceed with I2C scan - connection failed")
    # Still continue to power off and report
    psu.safe_power_off()
    psu.close()
    exit(1)

# Track I2C detection results
i2c_devices_found = 0
i2c_devices_total = 0
i2c_failures = []

if connection:
    # Send initial command
    print_info("\n  === I2C Bus Scan Starting ===")
    tcp.tcp_poke(1, 0x00)
    send_command(connection, INITIAL_COMMAND)

    # --- Scan Bus 0x00: SI5342 ---
    print_info("\n  [Bus 0x00] Scanning for SI5342...")
    readback = send_command(connection, 'i2cdetect -r -y 0')
    i2c_devices_total += 1
    if validate_i2c_device(readback, 'SI5342', '6b', result_dict):
        rp_dict.log06_PTB['SI5342'] = 'Detected'
        i2c_devices_found += 1
    else:
        rp_dict.log06_PTB['SI5342'] = 'No ...'
        i2c_failures.append('SI5342 at 0x6b')

    # --- Scan Bus 0x01: SI5344 ---
    print_info("\n  [Bus 0x01] Scanning for SI5344...")
    tcp.tcp_poke(1, 0x01)
    readback = send_command(connection, 'i2cdetect -r -y 0')
    i2c_devices_total += 1
    if validate_i2c_device(readback, 'SI5344', '6b', result_dict):
        rp_dict.log06_PTB['SI5344'] = 'Detected'
        i2c_devices_found += 1
    else:
        rp_dict.log06_PTB['SI5344'] = 'No ...'
        i2c_failures.append('SI5344 at 0x6b')

    # --- Scan Bus 0x02: TCA9546ADR ---
    print_info("\n  [Bus 0x02] Scanning for TCA9546ADR...")
    tcp.tcp_poke(1, 0x02)
    readback = send_command(connection, 'i2cdetect -r -y 0')
    Device = 'TCA9546ADR';    Address = '70'
    i2c_devices_total += 1
    if validate_i2c_device(readback, Device, Address, result_dict):
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
        i2c_devices_found += 1
    else:
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
        i2c_failures.append(f'{Device} at 0x{Address}')

    # --- Scan Bus 0x03: LTC2991 (multiple) and LTC2990 ---
    print_info("\n  [Bus 0x03] Scanning for LTC2991/LTC2990 devices...")
    tcp.tcp_poke(1, 0x03)
    readback = send_command(connection, 'i2cdetect -r -y 0')

    for Device, Address in [('LTC2991', '48'), ('LTC2991', '49'), ('LTC2991', '4a'), ('LTC2991', '4b'), ('LTC2990', '4e')]:
        i2c_devices_total += 1
        if validate_i2c_device(readback, Device, Address, result_dict):
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
            i2c_devices_found += 1
        else:
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
            i2c_failures.append(f'{Device} at 0x{Address}')


    # --- Scan Bus 0x04: TCA6424 devices ---
    print_info("\n  [Bus 0x04] Scanning for TCA6424 devices (I2C bus 2)...")
    tcp.tcp_poke(1, 0x04)
    readback = send_command(connection, 'i2cdetect -r -y 2')

    for Device, Address in [('TCA6424', '22'), ('TCA642', '23')]:
        i2c_devices_total += 1
        if validate_i2c_device(readback, Device, Address, result_dict):
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
            i2c_devices_found += 1
        else:
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
            i2c_failures.append(f'{Device} at 0x{Address}')

    # --- Scan Bus 0x05: Multiple devices (I2C bus 1) ---
    print_info("\n  [Bus 0x05] Scanning for LTC2499, INA226, AD7414A, SODIMM, LTC2991 (I2C bus 1)...")
    tcp.tcp_poke(1, 0x05)
    time.sleep(3)
    readback = send_command(connection, 'i2cdetect -r -y 1')

    bus_05_devices = [
        ('LTC2499', '15'),
        ('INA226', '46'),
        ('AD7414A', '49'),
        ('AD7414A', '4a'),
        ('AD7414A', '4d'),
        ('SODIMM', '51'),
        ('LTC2991', '48'),
        ('LTC2991', '4c'),
        ('LTC2991', '4e')
    ]

    for Device, Address in bus_05_devices:
        i2c_devices_total += 1
        if validate_i2c_device(readback, Device, Address, result_dict):
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
            i2c_devices_found += 1
        else:
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
            i2c_failures.append(f'{Device} at 0x{Address}')


    # --- Scan Bus 0x06: DAC7574 devices ---
    print_info("\n  [Bus 0x06] Scanning for DAC7574 devices...")
    tcp.tcp_poke(1, 0x06)
    readback = send_command(connection, 'i2cdetect -r -y 0')

    for Address in ['4c', '4d', '4e', '4f']:
        Device = 'DAC7574'
        i2c_devices_total += 1
        if validate_i2c_device(readback, Device, Address, result_dict):
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
            i2c_devices_found += 1
        else:
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
            i2c_failures.append(f'{Device} at 0x{Address}')

    # --- Scan Bus 0x07: LTC2977 ---
    print_info("\n  [Bus 0x07] Scanning for LTC2977...")
    tcp.tcp_poke(1, 0x07)
    readback = send_command(connection, 'i2cdetect -r -y 0')
    Device = 'LTC2977'
    Address = '5c'
    i2c_devices_total += 1
    if validate_i2c_device(readback, Device, Address, result_dict):
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
        i2c_devices_found += 1
    else:
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
        i2c_failures.append(f'{Device} at 0x{Address}')

    # --- Scan Bus 0x08: DAC7574 devices (I2C bus 1) ---
    print_info("\n  [Bus 0x08] Scanning for DAC7574 devices (I2C bus 1)...")
    tcp.tcp_poke(1, 0x08)
    readback = send_command(connection, 'i2cdetect -r -y 1')

    for Address in ['4c', '4d']:
        Device = 'DAC7574'
        i2c_devices_total += 1
        if validate_i2c_device(readback, Device, Address, result_dict):
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
            i2c_devices_found += 1
        else:
            rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
            i2c_failures.append(f'{Device} at 0x{Address}')

    # --- Scan Bus 0x09: 24LC64SN EEPROM ---
    print_info("\n  [Bus 0x09] Scanning for 24LC64SN EEPROM...")
    tcp.tcp_poke(1, 0x09)
    readback = send_command(connection, 'i2cdetect -r -y 0')
    Device = '24LC64SN'
    Address = '50'
    i2c_devices_total += 1
    if validate_i2c_device(readback, Device, Address, result_dict):
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
        i2c_devices_found += 1
    else:
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
        i2c_failures.append(f'{Device} at 0x{Address}')

    # --- Scan Bus 0x0a: ADN2814 ---
    print_info("\n  [Bus 0x0a] Scanning for ADN2814...")
    tcp.tcp_poke(1, 0x0a)
    readback = send_command(connection, 'i2cdetect -y 0')
    Device = 'ADN2814'
    Address = '40'
    i2c_devices_total += 1
    if validate_i2c_device(readback, Device, Address, result_dict):
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'Detected'
        i2c_devices_found += 1
    else:
        rp_dict.log06_PTB['{} 0x{}'.format(Device, Address)] = 'No'
        i2c_failures.append(f'{Device} at 0x{Address}')

    # === I2C Scan Summary ===
    print_header("I2C Scan Summary")
    print_info(f"  Devices Found: {i2c_devices_found} / {i2c_devices_total}")
    if i2c_failures:
        print_fail(f"  Missing Devices: {len(i2c_failures)}")
        for dev in i2c_failures:
            print_fail(f"    - {dev}")
        show_i2c_troubleshoot()
    else:
        print_pass("  All I2C devices detected successfully!")
time.sleep(0.5)

# Close connection
if connection:
    connection.close()
    print_info("  WIB connection closed.")

# Log errors to result_dict
if result_dict.get("error_log"):
    print_warning(f"\n  Total errors logged: {len(result_dict['error_log'])}")

# Update CSV with all I2C device detection results
if rp_dict.csv_manager:
    # Map device names to CSV item IDs
    device_mapping = {
        'SI5342': 'T05_10',
        'SI5344': 'T05_11',
        'TCA9546ADR 0x70': 'T05_12',
        'LTC2991 0x48': 'T05_13',
        'LTC2991 0x49': 'T05_14',
        'LTC2991 0x4a': 'T05_15',
        'LTC2991 0x4b': 'T05_16',
        'LTC2990 0x4e': 'T05_17',
        'TCA6424 0x22': 'T05_18',
        'TCA642 0x23': 'T05_19',
        'LTC2499 0x15': 'T05_20',
        'INA226 0x46': 'T05_21',
        'AD7414A 0x49': 'T05_22',
        'AD7414A 0x4a': 'T05_23',
        'AD7414A 0x4d': 'T05_24',
        'SODIMM 0x51': 'T05_25',
        'DAC7574 0x4c': 'T05_29',
        'DAC7574 0x4d': 'T05_30',
        'DAC7574 0x4e': 'T05_31',
        'DAC7574 0x4f': 'T05_32',
        'LTC2977 0x5c': 'T05_33',
        '24LC64SN 0x50': 'T05_36',
        'ADN2814 0x40': 'T05_37'
    }

    updates = []
    for device_name, item_id in device_mapping.items():
        device_status = rp_dict.log06_PTB.get(device_name, "Not Tested")
        csv_status = "PASS" if "Detected" in device_status else "FAIL"
        updates.append({
            "item_id": item_id,
            "value": device_status,
            "status": csv_status
        })

    rp_dict.csv_manager.batch_update(updates)

psu.safe_power_off()
psu.close()
t2 = time.time()
test_duration = round(t2-t1, 2)

# Final test summary
print_header("Test05 Complete")
print_info(f"  Test Duration: {test_duration} seconds")
if i2c_failures:
    print_fail(f"  Overall Status: FAIL ({len(i2c_failures)} devices missing)")
else:
    print_pass("  Overall Status: PASS (All devices detected)")

# Update CSV with test duration
if rp_dict.csv_manager:
    rp_dict.csv_manager.update_item("T05_99", test_duration, status="COMPLETE")



import os

# Determine overall status
all_devices_detected = all("Detected" in str(value) for value in rp_dict.log06_PTB.values())
overall_pass = all_devices_detected
overall_status = "PASS" if overall_pass else "FAIL"
overall_status_class = "status-pass" if overall_pass else "status-fail"

# === Setup report path with pass/fail suffix ===
report_filename = get_report_filename("Test05_I2C_Device_report", overall_pass)
target_file_path = get_report_path(report_filename)
print(f"Report path: {target_file_path}")

# Count detected devices
total_devices = len(rp_dict.log06_PTB)
detected_devices = sum(1 for value in rp_dict.log06_PTB.values() if "Detected" in str(value))

# Build device table rows
device_rows = ""
for key, value in rp_dict.log06_PTB.items():
    status_class = "status-pass" if "Detected" in value else "status-fail"
    status_text = "PASS" if "Detected" in value else "FAIL"
    device_rows += f"<tr><td>{key}</td><td>{value}</td><td class='{status_class}'>{status_text}</td></tr>\n"

# HTML content with professional clean styling
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WIB I2C Device Search Report - Test05</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #ffffff;
            color: #000000;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        .header {{
            border-bottom: 2px solid #000000;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: bold;
        }}
        .subtitle {{
            font-size: 18px;
            color: #333333;
            margin-top: 5px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            margin: 10px 0;
            font-weight: bold;
            border: 2px solid #000000;
        }}
        .status-pass {{
            background-color: #ffffff;
            color: #000000;
        }}
        .status-fail {{
            background-color: #fee2e2;
            color: #000000;
        }}
        .info-section {{
            margin: 20px 0;
            padding: 15px;
            background-color: #f5f5f5;
            border: 1px solid #cccccc;
        }}
        .info-row {{
            display: flex;
            padding: 5px 0;
        }}
        .info-label {{
            font-weight: bold;
            min-width: 200px;
        }}
        .info-value {{
            flex: 1;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: #ffffff;
        }}
        th, td {{
            border: 1px solid #000000;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background-color: #e5e5e5;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #cccccc;
            text-align: center;
            color: #666666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>DUNE WIB Quality Control</h1>
            <div class="subtitle">I2C Device Search Report (Test05)</div>
            <div class="status-badge {overall_status_class}">Overall Status: {overall_status}</div>
        </div>

        <!-- Test Information -->
        <div class="info-section">
            <div class="info-row">
                <div class="info-label">Test Date:</div>
                <div class="info-value">{datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Test Duration:</div>
                <div class="info-value">{test_duration} seconds</div>
            </div>
            <div class="info-row">
                <div class="info-label">Devices Detected:</div>
                <div class="info-value">{detected_devices} / {total_devices}</div>
            </div>
            <div class="info-row">
                <div class="info-label">WIB IP Address:</div>
                <div class="info-value">192.168.121.1</div>
            </div>
        </div>

        <!-- Power Measurements -->
        <h2>WIB Power Supply</h2>
        <table>
            <thead>
                <tr>
                    <th>Channel</th>
                    <th>Voltage (V)</th>
                    <th>Current (A)</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Channel 1</td>
                    <td>{v1:.3f}</td>
                    <td>{c1:.3f}</td>
                    <td class="{'status-pass' if 11.0 <= v1 <= 13.0 and 0.5 <= c1 <= 3.0 else 'status-fail'}">{'PASS' if 11.0 <= v1 <= 13.0 and 0.5 <= c1 <= 3.0 else 'FAIL'}</td>
                </tr>
                <tr>
                    <td>Channel 2</td>
                    <td>{v2:.3f}</td>
                    <td>{c2:.3f}</td>
                    <td class="{'status-pass' if 11.0 <= v2 <= 13.0 and 0.5 <= c2 <= 3.0 else 'status-fail'}">{'PASS' if 11.0 <= v2 <= 13.0 and 0.5 <= c2 <= 3.0 else 'FAIL'}</td>
                </tr>
            </tbody>
        </table>

        <!-- I2C Device Detection Results -->
        <h2>I2C Device Detection Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Device Name & Address</th>
                    <th>Detection Result</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {device_rows}
            </tbody>
        </table>

        <!-- Footer -->
        <div class="footer">
            <p>Generated by DUNE WIB QC System - Test05: I2C Device Search</p>
            <p>Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Made by Lingyun Ke</p>
        </div>
    </div>
</body>
</html>
"""

# Always create new file (overwrite if exists)
with open(target_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML report saved (new file) to {target_file_path}")















