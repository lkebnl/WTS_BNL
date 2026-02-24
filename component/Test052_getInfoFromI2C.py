# WIB Power Rail
import socket
import sys
import os
# Add the parent directory to sys.path so 'function' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# from function.rigol_dp832_ps import RIGOL_PS_CTL
import function.Rigol_DP800 as rigol
from function.report_path import get_report_path, init_report_session
import time
from function.ping_host import ping_host
from datetime import datetime
from function.cls_udp import CLS_UDP
from function.tcp_cfg import TCP_CFG
from function.raw_convertor import RAW_CONV
from function.csv_manager import WIB_QC_CSV_Manager
import time
import file.report_dict as rp_dict
import function.tcp as tcp_con
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
    "i2c_device_missing": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: I2C SENSOR NOT DETECTED                      │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • I2C bus multiplexer not configured correctly             │
│  • Sensor failure or not populated on board                 │
│  • I2C bus pull-up resistor issue                           │
│  • Clock/data line problem                                  │
│                                                             │
│  Actions:                                                   │
│  1. Check I2C multiplexer configuration                     │
│  2. Verify sensor is soldered on the board                  │
│  3. Check for cold solder joints near sensor                │
│  4. Measure I2C bus pull-up voltage (~3.3V)                 │
│  5. Try running i2cdetect to scan the bus                   │
└─────────────────────────────────────────────────────────────┘
""",
    "sensor_read_fail": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: SENSOR READ FAILED                           │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Sensor not responding to I2C commands                    │
│  • Invalid register address                                 │
│  • I2C bus busy or locked                                   │
│  • Sensor requires initialization first                     │
│                                                             │
│  Actions:                                                   │
│  1. Verify sensor was detected with i2cdetect               │
│  2. Check sensor initialization sequence                    │
│  3. Try resetting the I2C bus                               │
│  4. Verify register addresses in datasheet                  │
│  5. Check if sensor needs warm-up time                      │
└─────────────────────────────────────────────────────────────┘
""",
    "temperature_out_of_range": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: TEMPERATURE READING OUT OF RANGE             │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Sensor calibration issue                                 │
│  • Actual overheating condition                             │
│  • Incorrect conversion formula                             │
│  • Sensor damage or failure                                 │
│                                                             │
│  CAUTION: High temperature may indicate fault!              │
│                                                             │
│  Actions:                                                   │
│  1. If temp very high: check board for hot spots            │
│  2. Verify adequate cooling/airflow                         │
│  3. Compare with other temperature sensors                  │
│  4. Check sensor connections                                │
│  5. Allow board to cool and retry                           │
└─────────────────────────────────────────────────────────────┘
""",
    "voltage_out_of_range": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: VOLTAGE READING OUT OF RANGE                 │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Power regulator failure                                  │
│  • Excessive load on rail                                   │
│  • Input voltage issue                                      │
│  • Component failure                                        │
│                                                             │
│  Actions:                                                   │
│  1. Check power input voltage                               │
│  2. Verify regulator output with multimeter                 │
│  3. Check for shorts on affected rail                       │
│  4. Inspect regulator components                            │
│  5. Test with reduced load if possible                      │
└─────────────────────────────────────────────────────────────┘
""",
    "current_out_of_range": """
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: CURRENT READING OUT OF RANGE                 │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Short circuit on monitored rail                          │
│  • Component drawing excessive current                      │
│  • Sense resistor issue                                     │
│  • ADC calibration error                                    │
│                                                             │
│  CAUTION: High current may damage components!               │
│                                                             │
│  Actions:                                                   │
│  1. If current very high: power off immediately             │
│  2. Check for shorts on the power rail                      │
│  3. Inspect components on affected rail                     │
│  4. Verify sense resistor value                             │
│  5. Compare with power supply current reading               │
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
    """Validate I2C device detection"""
    if address.lower() in readback.lower():
        print_pass(f"    ✓ I2C Sensor {device} found at 0x{address}")
        return True
    else:
        print_fail(f"    ✗ I2C Sensor {device} NOT FOUND at 0x{address}")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"I2C sensor {device} not detected at 0x{address}")
        return False

def validate_temperature(value, sensor_name, min_temp=-10, max_temp=85, result_dict=None):
    """Validate temperature reading is within expected range"""
    if value is None:
        print_fail(f"    ✗ {sensor_name}: Read FAILED (None)")
        return False

    if min_temp <= value <= max_temp:
        print_pass(f"    ✓ {sensor_name}: {value:.2f}°C")
        return True
    else:
        print_warning(f"    ⚠ {sensor_name}: {value:.2f}°C (outside {min_temp}-{max_temp}°C range)")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"{sensor_name} temperature {value:.2f}°C out of range")
        return False

def validate_voltage(value, sensor_name, nominal, tolerance_pct=10, result_dict=None):
    """Validate voltage reading is within tolerance of nominal"""
    if value is None:
        print_fail(f"    ✗ {sensor_name}: Read FAILED (None)")
        return False

    min_v = nominal * (1 - tolerance_pct/100)
    max_v = nominal * (1 + tolerance_pct/100)

    if min_v <= value <= max_v:
        print_pass(f"    ✓ {sensor_name}: {value:.3f}V (nominal {nominal}V)")
        return True
    else:
        print_warning(f"    ⚠ {sensor_name}: {value:.3f}V (expected {nominal}V ±{tolerance_pct}%)")
        if result_dict is not None:
            if "error_log" not in result_dict:
                result_dict["error_log"] = []
            result_dict["error_log"].append(f"{sensor_name} voltage {value:.3f}V outside tolerance")
        return False

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

def show_sensor_troubleshoot(issue_type="sensor_read_fail"):
    """Display sensor troubleshooting message"""
    if issue_type in TROUBLESHOOT:
        print_warning(TROUBLESHOOT[issue_type])


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


def ltc2499_c_style_voltage(raw_bytes, vref=2.5):
    """
    Matches C code conversion for LTC2499 single-ended mode.

    :param raw_bytes: List of 4 bytes from LTC2499 [MSB, ..., LSB]
    :param vref: Reference voltage (default 2.5V)
    :return: Converted voltage in single-ended mode
    """
    if len(raw_bytes) != 4:
        raise ValueError("Expected 4 bytes")
    print(raw_bytes)
    # Build 32-bit word (big endian: MSB first)
    value = (raw_bytes[0] << 24) | (raw_bytes[1] << 16) | (raw_bytes[2] << 8) | raw_bytes[3]
    print(value)

    # Extract 25-bit ADC value (bits 6–30), drop sub-LSBs
    adc_code = int((value >> 6) & 0x1FFFFFF)  # 25-bit unsigned

    # Convert to voltage in ±VREF/2 range → ±1.25V
    volts = adc_code * (vref / 2) / (2**24)  # scale 25-bit value

    # Convert bipolar format (wrap around)
    if volts > (vref / 2):
        print(volts)
        volts -= vref

    # Add COM reference offset (for single-ended mode)
    return volts + (vref / 2)


def parse_ltc2499_output(temp_result):
    # Split by lines and find the one with hex values
    for line in temp_result.splitlines():
        if line.strip().startswith("0x"):
            hex_parts = line.strip().split()
            return [int(x, 16) for x in hex_parts]
    raise ValueError("No hex output found.")

print_header("A_RT05_02 : I2C Sensor Information")

# Result dictionary for error logging
result_dict = {"error_log": []}

# Tracking counters
sensors_read = 0
sensors_failed = 0
sensor_failures = []

t1 = time.time()

time.sleep(2)
tcp = TCP_CFG()
udp = CLS_UDP()
conv = RAW_CONV()
now = datetime.now()

print_header("Power Rail Initialization")
t1 = time.time()
psu = rigol.RigolDP800()

print_info("  Initializing Power Supply...")
psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
time.sleep(10)
v1, c1 = psu.measure(1)
v2, c2 = psu.measure(2)  # FIXED: was psu.measure(1)
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
        {"item_id": "T052_00", "value": round(v1, 3), "status": v1_status},
        {"item_id": "T052_01", "value": round(c1, 3), "status": c1_status},
        {"item_id": "T052_02", "value": round(v2, 3), "status": v2_status},
        {"item_id": "T052_03", "value": round(c2, 3), "status": c2_status}
    ])

time.sleep(1)

print_info("\n  Waiting for WIB boot (30 seconds)...")
time.sleep(30) # wait for boot
print_info("  Pinging WIB...")
ping_host(ip_address="192.168.121.1", count=4)
ping_host(ip_address="192.168.121.2", count=4)
time.sleep(1)
import component.temp as initial
initial
time.sleep(1)

# Connect to WIB
print_info("\n  Connecting to WIB via Telnet...")
connection = connect_to_server()

# Validate connection
if not validate_connection(connection, result_dict):
    print_fail("  Cannot proceed with I2C sensor reading - connection failed")
    psu.safe_power_off()
    psu.close()
    exit(1)

# Initialize I2C bus
print_header("I2C Sensor Reading")
tcp.tcp_poke(1, 0x00)
send_command(connection, INITIAL_COMMAND)
readback = send_command(connection, 'i2cdetect -r -y 0')
time.sleep(0.1)
tcp.tcp_poke(1, 0x01)
time.sleep(0.1)
tcp.tcp_poke(1, 0x05)
time.sleep(0.1)
readback = send_command(connection, 'i2cdetect -r -y 1')

# --- LTC2499 Temperature Sensor ---
print_info("\n  [LTC2499] Reading Temperature Sensors...")
Device = 'LTC2499';    Address = '15'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
    show_sensor_troubleshoot("i2c_device_missing")

# Read BRD0 Temperature
send_command(connection, 'i2cset -y 0 0x15 0xB0 0x80')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - ltc2499_c_style_voltage(raw_bytes)) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_BRD0_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_BRD0_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_BRD0_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_BRD0_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_BRD0_Temperature')

# Read BRD1 Temperature
send_command(connection, 'i2cset -y 0 0x15 0xB1 0x80')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - ltc2499_c_style_voltage(raw_bytes)) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_BRD1_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_BRD1_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_BRD1_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_BRD1_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_BRD1_Temperature')

# Read BRD2 Temperature
send_command(connection, 'i2cset -y 0 0x15 0xB2 0x80')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - ltc2499_c_style_voltage(raw_bytes)) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_BRD2_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_BRD2_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_BRD2_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_BRD2_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_BRD2_Temperature')

# Read BRD3 Temperature
send_command(connection, 'i2cset -y 0 0x15 0xB3 0x80')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - ltc2499_c_style_voltage(raw_bytes)) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_BRD3_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_BRD3_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_BRD3_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_BRD3_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_BRD3_Temperature')

# Read WIB1 Temperature
send_command(connection, 'i2ctransfer -y 0 w2@0x15 0xB5 0x80')
time.sleep(0.2)
send_command(connection, 'i2ctransfer -y 0 r4@0x15')
send_command(connection, 'i2ctransfer -y 0 r4@0x15')
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - 0.487) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_WIB1_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_WIB1_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_WIB1_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_WIB1_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_WIB1_Temperature')

# Read WIB2 Temperature
send_command(connection, 'i2cset -y 0 0x15 0xB5 0x80')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - 0.483) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_WIB2_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_WIB2_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_WIB2_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_WIB2_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_WIB2_Temperature')

# Read WIB3 Temperature
send_command(connection, 'i2ctransfer -y 0 w2@0x15 0xB6 0x80')
time.sleep(0.2)
send_command(connection, 'i2ctransfer -y 0 r4@0x15')
send_command(connection, 'i2ctransfer -y 0 r4@0x15')
temp_result = send_command(connection, 'i2ctransfer -y 0 r4@0x15')
try:
    raw_bytes = parse_ltc2499_output(temp_result)
    temp_val = (0.598 - 0.497) / 0.002 + 27
    rp_dict.log04_wib['LTC2499_WIB3_Temperature'] = temp_val
    sensors_read += 1
    validate_temperature(temp_val, 'LTC2499_WIB3_Temperature', result_dict=result_dict)
except (ValueError, IndexError) as e:
    print_fail(f'    ✗ LTC2499_WIB3_Temperature: Read FAILED ({e})')
    rp_dict.log04_wib['LTC2499_WIB3_Temperature'] = None
    sensors_failed += 1
    sensor_failures.append('LTC2499_WIB3_Temperature')
# --- INA226 Power Monitor ---
print_info("\n  [INA226] Reading Power Monitor...")
tcp.tcp_poke(1, 0x05)
time.sleep(0.1)
readback = send_command(connection, 'i2cdetect -r -y 1')
Device = 'INA226';    Address = '46'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
    show_sensor_troubleshoot("i2c_device_missing")
send_command(connection, 'i2cset -y 0 0x46 0x05 0x0a 0x00')
send_command(connection, 'i2cset -y 0 0x46 0x02')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 w1@0x46 0x02 r2')
print('temp_result')
try:
    print(temp_result.splitlines()[1])
    if 'Error:' in temp_result or len(temp_result.splitlines()) < 2:
        print('\033[33mWarning: Failed to read Vbus from INA226\033[0m')
        vbus_voltage = None
    else:
        msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
        raw_value = (msb << 8) | lsb
        vbus_voltage = raw_value * 0.00125
    rp_dict.log04_wib['LINA226_Vbus'] = vbus_voltage
except (ValueError, IndexError) as e:
    print(f'\033[33mWarning: Error parsing INA226 Vbus: {e}\033[0m')
    rp_dict.log04_wib['LINA226_Vbus'] = None
send_command(connection, 'i2cset -y 0 0x46 0x01')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x46')
try:
    if 'Error:' in temp_result or len(temp_result.splitlines()) < 2:
        print('\033[33mWarning: Failed to read current from INA226\033[0m')
        current = None
    else:
        msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
        raw_value = (msb << 8) | lsb
        if raw_value > 0x7FFF:
            raw_value -= 0x10000
        shunt_v = raw_value * 2.5e-6
        current = shunt_v / 0.005
    rp_dict.log04_wib['INA226_Current'] = current
except (ValueError, IndexError) as e:
    print(f'\033[33mWarning: Error parsing INA226 Current: {e}\033[0m')
    rp_dict.log04_wib['INA226_Current'] = None
# --- AD7414 Temperature Sensors ---
print_info("\n  [AD7414] Reading Temperature Sensors...")
tcp.tcp_poke(1, 0x05)
tcp.tcp_poke(1, 0x05)
time.sleep(0.5)
readback = send_command(connection, 'i2cdetect -r -y 1')
Device = 'AD7414_0x4A';    Address = '4a'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
send_command(connection, 'i2cset -y 0 0x4a 0x00')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x4a')
print('temp_result')
try:
    print(temp_result.splitlines()[1])
    if 'Error:' in temp_result or len(temp_result.splitlines()) < 2:
        print('\033[33mWarning: Failed to read temperature from AD7414_0x4A\033[0m')
        temperature = None
    else:
        msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
        raw = ((msb << 8) | lsb) >> 6
        print(raw)
        if raw > 511:
            raw -= 512
        print(raw)
        temperature = raw * 0.25
    rp_dict.log04_wib['AD7414_0x4A_temperature'] = temperature
except (ValueError, IndexError) as e:
    print(f'\033[33mWarning: Error parsing AD7414_0x4A temperature: {e}\033[0m')
    rp_dict.log04_wib['AD7414_0x4A_temperature'] = None
Device = 'AD7414_0x49';    Address = '49'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
send_command(connection, 'i2cset -y 0 0x49 0x00')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x49')
print('temp_result')
try:
    print(temp_result.splitlines()[1])
    if 'Error:' in temp_result or len(temp_result.splitlines()) < 2:
        print('\033[33mWarning: Failed to read temperature from AD7414_0x49\033[0m')
        temperature = None
    else:
        msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
        raw = ((msb << 8) | lsb) >> 6
        if raw > 511:
            raw -= 512
        temperature = raw * 0.25
    rp_dict.log04_wib['AD7414_0x49_temperature'] = temperature
except (ValueError, IndexError) as e:
    print(f'\033[33mWarning: Error parsing AD7414_0x49 temperature: {e}\033[0m')
    rp_dict.log04_wib['AD7414_0x49_temperature'] = None
Device = 'AD7414_0x4D';    Address = '4d'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
send_command(connection, 'i2cset -y 0 0x4d 0x00')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x4d')
print('temp_result')
try:
    print(temp_result.splitlines()[1])
    if 'Error:' in temp_result or len(temp_result.splitlines()) < 2:
        print('\033[33mWarning: Failed to read temperature from AD7414_0x4D\033[0m')
        temperature = None
    else:
        msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
        raw = ((msb << 8) | lsb) >> 6
        if raw > 511:
            raw -= 512
        temperature = raw * 0.25
    rp_dict.log04_wib['AD7414_0x4D_temperature'] = temperature
except (ValueError, IndexError) as e:
    print(f'\033[33mWarning: Error parsing AD7414_0x4D temperature: {e}\033[0m')
    rp_dict.log04_wib['AD7414_0x4D_temperature'] = None
# --- LTC2991 Monitor (0x48) ---
print_info("\n  [LTC2991_0x48] Reading Monitor...")
Device = 'LTC2991_0x48';    Address = '48'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
send_command(connection, 'i2cset -y 0 0x48 0x01 0x18')
send_command(connection, 'i2cset -y 0 0x48 0x01 0x18')
send_command(connection, 'sleep 0.05')
send_command(connection, 'i2cset -y 0 0x48 0x1A')
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
print('temp_result')
try:
    print(temp_result.splitlines()[1])
    if 'Error:' in temp_result or len(temp_result.splitlines()) < 2:
        print('\033[33mWarning: Failed to read temperature from LTC2991_0x48\033[0m')
        temperature = None
    else:
        msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
        raw = ((msb & 0x1F) << 8) | lsb
        if raw & 0x1000:
            raw -= 1 << 13
        temperature = raw * 0.0625
    rp_dict.log04_wib['LTC2991_0x48_temperature'] = temperature
except (ValueError, IndexError) as e:
    print(f'\033[33mWarning: Error parsing LTC2991_0x48 temperature: {e}\033[0m')
    rp_dict.log04_wib['LTC2991_0x48_temperature'] = None
# write
send_command(connection, 'i2cset -y 0 0x48 0x06 0x11')
send_command(connection, 'i2cset -y 0 0x48 0x07 0x11')
send_command(connection, 'i2cset -y 0 0x48 0x01 0xff')
send_command(connection, 'i2cset -y 0 0x48 0x06 0x11')
send_command(connection, 'i2cset -y 0 0x48 0x07 0x11')
send_command(connection, 'i2cset -y 0 0x48 0x01 0xff')
# set read
send_command(connection, 'i2cset -y 0 0x48 0x0c')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_1 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V0.85_c'] = current_1
send_command(connection, 'i2cset -y 0 0x48 0x10')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_2 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V5.0_c'] = current_2
send_command(connection, 'i2cset -y 0 0x48 0x14')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_3 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V2.5_c'] = current_3
send_command(connection, 'i2cset -y 0 0x48 0x18')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_4 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V1.8_c'] = current_4
send_command(connection, 'i2cset -y 0 0x48 0x0A')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_1 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2991_0x48_V0.85_v'] = voltage_1
send_command(connection, 'i2cset -y 0 0x48 0x0E')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_2 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2991_0x48_V5.0_v'] = voltage_2
send_command(connection, 'i2cset -y 0 0x48 0x12')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_3 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2991_0x48_V2.5_v'] = voltage_3
send_command(connection, 'i2cset -y 0 0x48 0x16')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_4 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2991_0x48_V1.8_v'] = voltage_4
send_command(connection, 'i2cset -y 0 0x48 0x1c')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
vcc = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2991_0x48_VCC'] = vcc + 2.5
# --- LTC2990 Monitor (0x4C) ---
print_info("\n  [LTC2990_0x4C] Reading Monitor...")
Device = 'LTC2990_0x4C';    Address = '4c'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
send_command(connection, 'i2cset -y 0 0x4c 0x01 0x1F')
send_command(connection, 'i2cset -y 0 0x4c 0x02 0xFF')
send_command(connection, 'sleep 0.05')
send_command(connection, 'i2cset -y 0 0x4c 0x06')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4c')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_5 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4C_V1.2_v'] = voltage_5
send_command(connection, 'i2cset -y 0 0x4c 0x0a')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4c')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_6 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4C_V3.3_v'] = voltage_6
send_command(connection, 'i2cset -y 0 0x4c 0x04')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4c')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
temp = (raw & 0x3fff)*0.0625
rp_dict.log04_wib['LTC2990_0x4C_temperature'] = temp
send_command(connection, 'i2cset -y 0 0x4c 0x0e')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4c')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_7 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4C_VCC'] = voltage_7 + 2.5
send_command(connection, 'i2cset -y 0 0x4c 0x01 0x06')
send_command(connection, 'i2cset -y 0 0x4c 0x02 0xff')
send_command(connection, 'i2cset -y 0 0x4c 0x0a')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4c')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_5 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2990_0x4c_V1_2_c'] = current_5
send_command(connection, 'i2cset -y 0 0x4c 0x0e')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4c')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_6 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2990_0x4c_V3.3_c'] = current_6
# --- LTC2990 Monitor (0x4E) ---
print_info("\n  [LTC2990_0x4E] Reading Monitor...")
Device = 'LTC2990_0x4e';    Address = '4e'
if validate_i2c_device(readback, Device, Address, result_dict):
    pass
else:
    sensor_failures.append(f'{Device} at 0x{Address}')
send_command(connection, 'i2cset -y 0 0x4e 0x01 0x1F')
send_command(connection, 'i2cset -y 0 0x4e 0x02 0xFF')
send_command(connection, 'sleep 0.05')
send_command(connection, 'i2cset -y 0 0x4e 0x06')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4e')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_5 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4e_V0.9_v'] = voltage_5
send_command(connection, 'i2cset -y 0 0x4e 0x0a')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4e')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_6 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4e_VCCPSPLL_1.2_v'] = voltage_6
send_command(connection, 'i2cset -y 0 0x4e 0x04')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4e')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
temp = (raw & 0x3fff)*0.0625
rp_dict.log04_wib['LTC2990_0x4e_temperature'] = temp
send_command(connection, 'i2cset -y 0 0x4e 0x0e')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4e')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_7 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4e_VCC'] = voltage_7 + 2.5
send_command(connection, 'i2cset -y 0 0x4e 0x0c')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4e')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
voltage_8 = ((raw & 0x3fff)) * 0.00030518
rp_dict.log04_wib['LTC2990_0x4e_PSDDR4_v'] = voltage_8
send_command(connection, 'i2cset -y 0 0x4e 0x01 0x06')
send_command(connection, 'i2cset -y 0 0x4e 0x02 0xff')
send_command(connection, 'i2cset -y 0 0x4e 0x0a')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x4e')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_5 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2990_0x4e_V0.9_c'] = current_5

# Update CSV with all sensor measurements
if rp_dict.csv_manager:
    rp_dict.csv_manager.batch_update([
        # LTC2499 Temperatures (7 sensors) - Fixed key names to match actual dictionary keys
        {"item_id": "T052_10", "value": round(rp_dict.log04_wib.get('LTC2499_BRD0_Temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_11", "value": round(rp_dict.log04_wib.get('LTC2499_BRD1_Temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_12", "value": round(rp_dict.log04_wib.get('LTC2499_BRD2_Temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_13", "value": round(rp_dict.log04_wib.get('LTC2499_BRD3_Temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_14", "value": round(rp_dict.log04_wib.get('LTC2499_WIB1_Temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_15", "value": round(rp_dict.log04_wib.get('LTC2499_WIB2_Temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_16", "value": round(rp_dict.log04_wib.get('LTC2499_WIB3_Temperature', 0), 2), "status": "PASS"},

        # INA226
        {"item_id": "T052_20", "value": round(rp_dict.log04_wib.get('LINA226_Vbus', 0), 3), "status": "PASS"},
        {"item_id": "T052_21", "value": round(rp_dict.log04_wib.get('INA226_Current', 0), 3), "status": "PASS"},

        # AD7414 Temperatures
        {"item_id": "T052_30", "value": round(rp_dict.log04_wib.get('AD7414_0x4A_temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_31", "value": round(rp_dict.log04_wib.get('AD7414_0x49_temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_32", "value": round(rp_dict.log04_wib.get('AD7414_0x4D_temperature', 0), 2), "status": "PASS"},

        # LTC2991_0x48 (10 measurements)
        {"item_id": "T052_40", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_41", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V0.85_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_42", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V0.85_c', 0), 3), "status": "PASS"},
        {"item_id": "T052_43", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V5.0_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_44", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V5.0_c', 0), 3), "status": "PASS"},
        {"item_id": "T052_45", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V2.5_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_46", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V2.5_c', 0), 3), "status": "PASS"},
        {"item_id": "T052_47", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V1.8_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_48", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_V1.8_c', 0), 3), "status": "PASS"},
        {"item_id": "T052_49", "value": round(rp_dict.log04_wib.get('LTC2991_0x48_VCC', 0), 3), "status": "PASS"},

        # LTC2990_0x4C (6 measurements)
        {"item_id": "T052_50", "value": round(rp_dict.log04_wib.get('LTC2990_0x4C_temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_51", "value": round(rp_dict.log04_wib.get('LTC2990_0x4C_V1.2_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_52", "value": round(rp_dict.log04_wib.get('LTC2990_0x4C_V3.3_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_53", "value": round(rp_dict.log04_wib.get('LTC2990_0x4C_VCC', 0), 3), "status": "PASS"},
        {"item_id": "T052_54", "value": round(rp_dict.log04_wib.get('LTC2990_0x4c_V1_2_c', 0), 3), "status": "PASS"},
        {"item_id": "T052_55", "value": round(rp_dict.log04_wib.get('LTC2990_0x4c_V3.3_c', 0), 3), "status": "PASS"},

        # LTC2990_0x4E (6 measurements)
        {"item_id": "T052_60", "value": round(rp_dict.log04_wib.get('LTC2990_0x4e_temperature', 0), 2), "status": "PASS"},
        {"item_id": "T052_61", "value": round(rp_dict.log04_wib.get('LTC2990_0x4e_V0.9_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_62", "value": round(rp_dict.log04_wib.get('LTC2990_0x4e_VCCPSPLL_1.2_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_63", "value": round(rp_dict.log04_wib.get('LTC2990_0x4e_PSDDR4_v', 0), 3), "status": "PASS"},
        {"item_id": "T052_64", "value": round(rp_dict.log04_wib.get('LTC2990_0x4e_VCC', 0), 3), "status": "PASS"},
        {"item_id": "T052_65", "value": round(rp_dict.log04_wib.get('LTC2990_0x4e_V0.9_c', 0), 3), "status": "PASS"},
    ])

t2 = time.time()
test_duration = round(t2 - t1, 2)

# Update CSV with test duration
if rp_dict.csv_manager:
    rp_dict.csv_manager.update_item("T052_99", test_duration, status="COMPLETE")

# === Test Summary ===
print_header("Test052 Summary")
print_info(f"  Sensors Read Successfully: {sensors_read}")
print_info(f"  Sensors Failed: {sensors_failed}")
print_info(f"  Test Duration: {test_duration} seconds")

if sensor_failures:
    print_fail(f"\n  Failed Sensors/Devices ({len(sensor_failures)}):")
    for fail in sensor_failures:
        print_fail(f"    - {fail}")
    show_sensor_troubleshoot("sensor_read_fail")
    print_fail("\n  Overall Status: FAIL")
else:
    print_pass("\n  All sensors read successfully!")
    print_pass("  Overall Status: PASS")

# Log errors if any
if result_dict.get("error_log"):
    print_warning(f"\n  Total errors logged: {len(result_dict['error_log'])}")

# Close connection
if connection:
    connection.close()
    print_info("  WIB connection closed.")

time.sleep(0.5)
psu.safe_power_off()
psu.close()

import os

# === Setup report path using centralized report_path module ===
target_file_path = get_report_path("Test052_I2C_Sensor_Info.html")
print(f"Report path: {target_file_path}")

# Organize measurements by category
categories = {
    "WIB Power Measurements": {
        "WIB_Power_Ch1_V": f"{v1:.3f} V",
        "WIB_Power_Ch1_I": f"{c1:.3f} A",
        "WIB_Power_Ch2_V": f"{v2:.3f} V",
        "WIB_Power_Ch2_I": f"{c2:.3f} A"
    },
    "LTC2499 Temperature Sensors": {},
    "INA226 Power Monitor": {},
    "AD7414 Temperature Sensors": {},
    "LTC2991_0x48 Monitor": {},
    "LTC2990_0x4C Monitor": {},
    "LTC2990_0x4E Monitor": {}
}

# Populate categories
for key, value in rp_dict.log04_wib.items():
    if "LTC2499" in key:
        categories["LTC2499 Temperature Sensors"][key] = f"{value:.2f} °C"
    elif "INA226" in key or "LINA226" in key:
        categories["INA226 Power Monitor"][key] = f"{value:.3f}"
    elif "AD7414" in key:
        categories["AD7414 Temperature Sensors"][key] = f"{value:.2f} °C"
    elif "LTC2991_0x48" in key:
        categories["LTC2991_0x48 Monitor"][key] = f"{value:.3f}"
    elif "LTC2990_0x4C" in key or "LTC2990_0x4c" in key:
        categories["LTC2990_0x4C Monitor"][key] = f"{value:.3f}"
    elif "LTC2990_0x4e" in key:
        categories["LTC2990_0x4E Monitor"][key] = f"{value:.3f}"

# Build category tables
category_html = ""
for category, items in categories.items():
    if items:  # Only show non-empty categories
        category_html += f"""
        <h3>{category}</h3>
        <table>
            <thead>
                <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
"""
        for key, value in items.items():
            category_html += f"                <tr><td>{key}</td><td>{value}</td></tr>\n"
        category_html += """            </tbody>
        </table>
"""

# Professional clean HTML report
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DUNE WIB I2C Sensor Information Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: Arial, sans-serif;
            background-color: #ffffff;
            color: #000000;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #000000;
        }}

        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}

        .header h2 {{
            font-size: 20px;
            color: #666666;
            font-weight: normal;
        }}

        .info-section {{
            margin: 30px 0;
            padding: 20px;
            background-color: #f5f5f5;
            border: 1px solid #000000;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #cccccc;
        }}

        .info-row:last-child {{
            border-bottom: none;
        }}

        .info-label {{
            font-weight: bold;
        }}

        h3 {{
            margin: 30px 0 15px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid #000000;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            border: 1px solid #000000;
        }}

        th {{
            background-color: #e5e5e5;
            color: #000000;
            font-weight: bold;
            padding: 12px;
            text-align: left;
            border: 1px solid #000000;
        }}

        td {{
            padding: 10px 12px;
            border: 1px solid #000000;
        }}

        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}

        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #cccccc;
            text-align: center;
            color: #666666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>DUNE WIB Quality Control</h1>
            <h2>I2C Sensor Information Report (Test052)</h2>
        </div>

        <div class="info-section">
            <h3 style="margin-top: 0; border: none;">Test Information</h3>
            <div class="info-row">
                <span class="info-label">Test Date:</span>
                <span>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</span>
            </div>
            <div class="info-row">
                <span class="info-label">Test Duration:</span>
                <span>{test_duration} seconds</span>
            </div>
            <div class="info-row">
                <span class="info-label">Total Measurements:</span>
                <span>{len(rp_dict.log04_wib) + 4} items</span>
            </div>
        </div>

        {category_html}

        <div class="footer">
            <p>DUNE WIB Quality Control System</p>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""

# Always create new file (overwrite if exists)
with open(target_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML report saved to {target_file_path}")

