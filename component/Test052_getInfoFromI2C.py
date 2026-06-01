# WIB Power Rail
import socket
import sys
import os
# Add the parent directory to sys.path so 'function' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# from function.rigol_dp832_ps import RIGOL_PS_CTL
import function.Rigol_DP800 as rigol
import time
from function.ping_host import ping_host
from datetime import datetime
from function.cls_udp import CLS_UDP
from function.tcp_cfg import TCP_CFG
from function.raw_convertor import RAW_CONV
import time
import file.report_dict as rp_dict
import function.tcp as tcp_con
from datetime import datetime
from function.report_path import get_report_path, get_result_csv_path, get_report_dir
from function.session_info import get_report_filename, get_session_info
from function.csv_manager import WIB_QC_CSV_Manager

SERVER_IP = "192.168.121.1"
PORT = 23  # Change if necessary (23 for Telnet, 22 for SSH)
USERNAME = "root"
PASSWORD = "root"
INITIAL_COMMAND = "i2cset -y 1 0x70 0xff 0xff"


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


# LTC2499 configuration
LTC2499_BUS  = 0
LTC2499_ADDR = 0x15
LTC2499_VREF = 2.578  # Actual circuit: 3.3V * 1K/(280+1K) ≈ 2.578V

LTC2499_CHANNELS = {
    'LTC2499_FEMB0_Temperature': 0,
    'LTC2499_FEMB1_Temperature': 1,
    'LTC2499_FEMB2_Temperature': 2,
    'LTC2499_FEMB3_Temperature': 3,
    'LTC2499_WIB1_Temperature':  4,
    'LTC2499_WIB2_Temperature':  5,
    'LTC2499_WIB3_Temperature':  6,
}


def ltc2499_c_style_voltage(raw_bytes, vref=2.578):
    """
    Convert LTC2499 raw 4 bytes to voltage.
    Matches C code: read_ltc2499_temp()

    :param raw_bytes: List of 4 bytes [MSB, ..., LSB]
    :param vref: Reference voltage. Circuit: 3.3V*1K/(280+1K) ≈ 2.578V
    :return: Converted voltage (single-ended, COM-referenced)
    """
    if len(raw_bytes) != 4:
        raise ValueError(f"Expected 4 bytes, got {len(raw_bytes)}")
    value = (raw_bytes[0] << 24) | (raw_bytes[1] << 16) | (raw_bytes[2] << 8) | raw_bytes[3]
    adc_code = (value >> 6) & 0x1FFFFFF
    half_vref = vref / 2.0
    volts = adc_code * half_vref / (2 ** 24)
    if volts > half_vref:
        volts -= 2 * half_vref
    volts += half_vref
    return volts


def parse_ltc2499_output(temp_result):
    """Parse i2ctransfer output, find the line starting with 0x and return bytes."""
    for line in temp_result.splitlines():
        if line.strip().startswith("0x"):
            hex_parts = line.strip().split()
            return [int(x, 16) for x in hex_parts]
    raise ValueError("No hex output found.")


def ltc2499_channel_byte(ch):
    """Compute first command byte for channel selection. Matches C: 0xB0 | ((ch%2)<<3) | (ch/2)"""
    return 0xB0 | ((ch % 2) << 3) | (ch // 2)


def read_ltc2499_all_temperatures(connection, bus, addr, channels, vref=2.578):
    """
    Read all LTC2499 temperature channels using writeread (matches C i2c_writeread).
    :return: dict {sensor_name: temperature_celsius or None}
    """
    results = {}
    channel_list = list(channels.items())
    first_ch = channel_list[0][1]
    byte0 = ltc2499_channel_byte(first_ch)
    send_command(connection, f'i2cset -y {bus} 0x{addr:02x} 0x{byte0:02x} 0x80')
    time.sleep(0.2)
    for i, (sensor_name, ch) in enumerate(channel_list):
        if i + 1 < len(channel_list):
            next_ch = channel_list[i + 1][1]
        else:
            next_ch = ch
        next_byte0 = ltc2499_channel_byte(next_ch)
        temp_result = send_command(
            connection,
            f'i2ctransfer -y {bus} w2@0x{addr:02x} 0x{next_byte0:02x} 0x80 r4@0x{addr:02x}'
        )
        try:
            raw_bytes = parse_ltc2499_output(temp_result)
            print(f'    {sensor_name} raw: {[hex(b) for b in raw_bytes]}')
            volts = ltc2499_c_style_voltage(raw_bytes, vref=vref)
            temp_val = (1.543 - volts) / 0.0033 - 273
            results[sensor_name] = temp_val
            print(f'    {sensor_name}: {temp_val:.2f} °C  (volts={volts:.4f}V)')
        except (ValueError, IndexError) as e:
            print(f'    \033[31m✗ {sensor_name}: Read FAILED ({e})\033[0m')
            results[sensor_name] = None
        time.sleep(0.2)
    return results

print("\033[35m" + "A_RT05_02 : I2C Sensor Information" + "\033[0m")

# Get session info (from WIB_QC_Detail.py or defaults for standalone run)
session_info = get_session_info()
wib_id = session_info.get('WIB_ID', 'standalone_test')

# Check if CSV exists in report folder; create if missing, attach if found
csv_path = get_result_csv_path()
if csv_path is None:
    report_dir = get_report_dir()
    csv_path = os.path.join(report_dir, f"WIB_{wib_id}_QC_Results.csv")
if not os.path.exists(csv_path):
    print(f"\nCSV not found — creating: {csv_path}")
    rp_dict.csv_manager = WIB_QC_CSV_Manager(wib_id, csv_filepath=csv_path, overwrite=True)
elif rp_dict.csv_manager is None:
    print(f"\nCSV found — attaching: {csv_path}")
    rp_dict.csv_manager = WIB_QC_CSV_Manager(wib_id, csv_filepath=csv_path, overwrite=False)

t1 = time.time()

time.sleep(2)
tcp = TCP_CFG()
udp = CLS_UDP()
conv = RAW_CONV()
now = datetime.now()

# print("\033[35m" + "A_RT03_01 : Power Rail" + "\033[0m")
t1 = time.time()
psu = rigol.RigolDP800()

psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
time.sleep(10)
v1, c1 = psu.measure(1)
v2, c2 = psu.measure(2)
time.sleep(1)

time.sleep(30) # wait for boot
print(c1)
print(c2)
ping_host(ip_address="192.168.121.1", count=4)
ping_host(ip_address="192.168.121.2", count=4)
time.sleep(1)
import component.temp as initial
initial
time.sleep(1)
# if __name__ == "__main__":

connection = connect_to_server()
if connection:
    pass
    # Send initial command
tcp.tcp_poke(1, 0x00)
send_command(connection, INITIAL_COMMAND)
readback = send_command(connection, 'i2cdetect -r -y 0')
print(readback)
time.sleep(0.1)
tcp.tcp_poke(1, 0x01)
time.sleep(0.1)
tcp.tcp_poke(1, 0x05)
time.sleep(0.1)
readback = send_command(connection, 'i2cdetect -r -y 1')
print(readback)
# --- LTC2499 Temperature Sensors ---
print("\033[36m\n  [LTC2499] Reading Temperature Sensors...\033[0m")
Device = 'LTC2499'; Address = '15'
if Address in readback:
    print(f'I2C Device {Device} has been found at 0x{Address}')
else:
    print(f'Loss I2C Device [{Device}] at 0x{Address} ...')

ltc2499_results = read_ltc2499_all_temperatures(
    connection,
    bus=LTC2499_BUS,
    addr=LTC2499_ADDR,
    channels=LTC2499_CHANNELS,
    vref=LTC2499_VREF
)
for sensor_name, temp_val in ltc2499_results.items():
    rp_dict.log04_wib[sensor_name] = temp_val
#########
# Send initial command
tcp.tcp_poke(1, 0x05)
time.sleep(0.1)
readback = send_command(connection, 'i2cdetect -r -y 1')
print(readback)
Device = 'LTC2499';    Address = '46'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
send_command(connection, 'i2cset -y 0 0x46 0x05 0x0a 0x00')
send_command(connection, 'i2cset -y 0 0x46 0x02')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 w1@0x46 0x02 r2')
print('temp_result')
print(temp_result.splitlines()[1])
msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
raw_value = (msb << 8) | lsb
vbus_voltage = raw_value * 0.00125
rp_dict.log04_wib['LINA226_Vbus'] = vbus_voltage
send_command(connection, 'i2cset -y 0 0x46 0x01')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x46')
msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
raw_value = (msb << 8) | lsb
if raw_value > 0x7FFF:
    raw_value -= 0x10000
shunt_v = raw_value * 2.5e-6
current = shunt_v / 0.005
rp_dict.log04_wib['INA226_Current'] = current
#######################
# Send initial command
tcp.tcp_poke(1, 0x05)
tcp.tcp_poke(1, 0x05)
time.sleep(0.5)
readback = send_command(connection, 'i2cdetect -r -y 1')
print(readback)
Device = 'AD7414_0x4A';    Address = '4a'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
send_command(connection, 'i2cset -y 0 0x4a 0x00')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x4a')
print('temp_result')
print(temp_result.splitlines()[1])
msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
raw = ((msb << 8) | lsb) >> 6
print(raw)
if raw > 511:
    raw -= 512
print(raw)
temperature = raw * 0.25
rp_dict.log04_wib['AD7414_0x4A_temperature'] = temperature
Device = 'AD7414_0x49';    Address = '49'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
send_command(connection, 'i2cset -y 0 0x49 0x00')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x49')
print('temp_result')
print(temp_result.splitlines()[1])
msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
raw = ((msb << 8) | lsb) >> 6
if raw > 511:
    raw -= 512
temperature = raw * 0.25
rp_dict.log04_wib['AD7414_0x49_temperature'] = temperature
Device = 'AD7414_0x4D';    Address = '4d'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
send_command(connection, 'i2cset -y 0 0x4d 0x00')
time.sleep(0.2)
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x4d')
print('temp_result')
print(temp_result.splitlines()[1])
msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
raw = ((msb << 8) | lsb) >> 6
if raw > 511:
    raw -= 512
temperature = raw * 0.25
rp_dict.log04_wib['AD7414_0x4D_temperature'] = temperature
###
Device = 'LTC2991_0x48';    Address = '48'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
send_command(connection, 'i2cset -y 0 0x48 0x01 0x18')
send_command(connection, 'i2cset -y 0 0x48 0x01 0x18')
send_command(connection, 'sleep 0.05')
send_command(connection, 'i2cset -y 0 0x48 0x1A')
temp_result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
print('temp_result')
print(temp_result.splitlines()[1])
msb, lsb = [int(x, 16) for x in temp_result.splitlines()[1].split()]
raw = ((msb & 0x1F) << 8) | lsb
if raw & 0x1000:
    raw -= 1 << 13
temperature = raw * 0.0625
rp_dict.log04_wib['LTC2991_0x48_temperature'] = temperature
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
current_1 = ((((raw & 0x3fff)) * 0.000019075) / 0.001)
rp_dict.log04_wib['LTC2991_0x48_V0.85_c'] = current_1
send_command(connection, 'i2cset -y 0 0x48 0x10')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_2 = ((((raw & 0x3fff)) * 0.000019075) / 0.001)
rp_dict.log04_wib['LTC2991_0x48_V5.0_c'] = current_2
send_command(connection, 'i2cset -y 0 0x48 0x14')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_3 = ((((raw & 0x3fff)) * 0.000019075) / 0.001)
rp_dict.log04_wib['LTC2991_0x48_V2.5_c'] = current_3
send_command(connection, 'i2cset -y 0 0x48 0x18')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_4 = ((((raw & 0x3fff)) * 0.000019075) / 0.001)
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
###
Device = 'LTC2990_0x4C';    Address = '4c'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
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
###
Device = 'LTC2990_0x4e';    Address = '4e'
if Address in readback:
    print('I2C Device {} has been found at 0x{}'.format(Device, Address))
else:
    print('Loss I2C Device [{}] at 0x{} ...'.format(Device, Address))
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

# Write all sensor results to QC CSV
if rp_dict.csv_manager:
    v1_status = "PASS" if 11.0 <= v1 <= 13.0 else "FAIL"
    v2_status = "PASS" if 11.0 <= v2 <= 13.0 else "FAIL"
    total_c_status = "PASS" if 1.1 <= (c1 + c2) <= 1.9 else "FAIL"
    updates = [
        {"item_id": "T052_00", "value": round(v1, 3), "status": v1_status},
        {"item_id": "T052_01", "value": round(c1, 3), "status": total_c_status},
        {"item_id": "T052_02", "value": round(v2, 3), "status": v2_status},
        {"item_id": "T052_03", "value": round(c2, 3), "status": total_c_status},
    ]
    sensor_map = [
        ("T052_10", "LTC2499_FEMB0_Temperature"),
        ("T052_11", "LTC2499_FEMB1_Temperature"),
        ("T052_12", "LTC2499_FEMB2_Temperature"),
        ("T052_13", "LTC2499_FEMB3_Temperature"),
        ("T052_14", "LTC2499_WIB1_Temperature"),
        ("T052_15", "LTC2499_WIB2_Temperature"),
        ("T052_16", "LTC2499_WIB3_Temperature"),
        ("T052_20", "LINA226_Vbus"),
        ("T052_21", "INA226_Current"),
        ("T052_30", "AD7414_0x4A_temperature"),
        ("T052_31", "AD7414_0x49_temperature"),
        ("T052_32", "AD7414_0x4D_temperature"),
        ("T052_40", "LTC2991_0x48_temperature"),
        ("T052_41", "LTC2991_0x48_V0.85_v"),
        ("T052_42", "LTC2991_0x48_V0.85_c"),
        ("T052_43", "LTC2991_0x48_V5.0_v"),
        ("T052_44", "LTC2991_0x48_V5.0_c"),
        ("T052_45", "LTC2991_0x48_V2.5_v"),
        ("T052_46", "LTC2991_0x48_V2.5_c"),
        ("T052_47", "LTC2991_0x48_V1.8_v"),
        ("T052_48", "LTC2991_0x48_V1.8_c"),
        ("T052_49", "LTC2991_0x48_VCC"),
        ("T052_50", "LTC2990_0x4C_temperature"),
        ("T052_51", "LTC2990_0x4C_V1.2_v"),
        ("T052_52", "LTC2990_0x4C_V3.3_v"),
        ("T052_53", "LTC2990_0x4C_VCC"),
        ("T052_54", "LTC2990_0x4c_V1_2_c"),
        ("T052_55", "LTC2990_0x4c_V3.3_c"),
        ("T052_60", "LTC2990_0x4e_temperature"),
        ("T052_61", "LTC2990_0x4e_V0.9_v"),
        ("T052_62", "LTC2990_0x4e_VCCPSPLL_1.2_v"),
        ("T052_63", "LTC2990_0x4e_PSDDR4_v"),
        ("T052_64", "LTC2990_0x4e_VCC"),
        ("T052_65", "LTC2990_0x4e_V0.9_c"),
    ]
    for item_id, key in sensor_map:
        val = rp_dict.log04_wib.get(key)
        status = "PASS" if val is not None else "FAIL"
        updates.append({"item_id": item_id, "value": round(val, 4) if val is not None else "", "status": status})
    rp_dict.csv_manager.batch_update(updates)
    t2 = time.time()
    rp_dict.csv_manager.update_item("T052_99", round(t2 - t1, 2), status="COMPLETE")

time.sleep(0.5)
psu.safe_power_off()
psu.close()

# === Determine overall pass/fail ===
overall_pass = all(v is not None for v in rp_dict.log04_wib.values())
overall_status = "PASS" if overall_pass else "FAIL"
overall_status_class = "status-pass" if overall_pass else "status-fail"

# === Setup report path with pass/fail suffix ===
report_filename = get_report_filename("Test052_I2C_Sensor_report", overall_pass)
target_file_path = get_report_path(report_filename)
print(f"Report path: {target_file_path}")

# Build sensor table rows
sensor_rows = ""
for key, value in rp_dict.log04_wib.items():
    if value is not None:
        row_status_class = "status-pass"
        sensor_rows += f"<tr><td>{key}</td><td>{value:.3f}</td><td class='{row_status_class}'>OK</td></tr>\n"
    else:
        row_status_class = "status-fail"
        sensor_rows += f"<tr><td>{key}</td><td>—</td><td class='{row_status_class}'>READ FAILED</td></tr>\n"

total_sensors = len(rp_dict.log04_wib)
ok_sensors = sum(1 for v in rp_dict.log04_wib.values() if v is not None)

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WIB I2C Sensor Report - Test052</title>
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
            <div class="subtitle">I2C Sensor Information Report (Test052)</div>
            <div class="status-badge {overall_status_class}">Overall Status: {overall_status}</div>
        </div>

        <!-- Test Information -->
        <div class="info-section">
            <div class="info-row">
                <div class="info-label">Test Date:</div>
                <div class="info-value">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Sensors Read OK:</div>
                <div class="info-value">{ok_sensors} / {total_sensors}</div>
            </div>
            <div class="info-row">
                <div class="info-label">WIB IP Address:</div>
                <div class="info-value">192.168.121.1</div>
            </div>
        </div>

        <!-- Power Supply -->
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
                    <td class="{'status-pass' if 11.0 <= v1 <= 13.0 else 'status-fail'}">{'PASS' if 11.0 <= v1 <= 13.0 else 'FAIL'}</td>
                </tr>
                <tr>
                    <td>Channel 2</td>
                    <td>{v2:.3f}</td>
                    <td>{c2:.3f}</td>
                    <td class="{'status-pass' if 11.0 <= v2 <= 13.0 else 'status-fail'}">{'PASS' if 11.0 <= v2 <= 13.0 else 'FAIL'}</td>
                </tr>
            </tbody>
        </table>

        <!-- Sensor Readings -->
        <h2>I2C Sensor Readings</h2>
        <table>
            <thead>
                <tr>
                    <th>Sensor</th>
                    <th>Value</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {sensor_rows}
            </tbody>
        </table>

        <!-- Footer -->
        <div class="footer">
            <p>Generated by DUNE WIB QC System - Test052: I2C Sensor Information</p>
            <p>Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Made by Lingyun Ke</p>
        </div>
    </div>
</body>
</html>
"""

with open(target_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML report saved to {target_file_path}")
