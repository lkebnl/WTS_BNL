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

SERVER_IP = "192.168.121.1"
PORT = 23  # Change if necessary (23 for Telnet, 22 for SSH)
USERNAME = "root"
PASSWORD = "root"
INITIAL_COMMAND = "i2cset -y 1 0x70 0xff 0xff"

# LTC2499 configuration
LTC2499_BUS  = 0
LTC2499_ADDR = 0x15
LTC2499_VREF = 2.578  # Actual circuit: 3.3V * 1K/(280+1K) ≈ 2.578V

# Channel mapping: sensor name -> channel number
LTC2499_CHANNELS = {
    'LTC2499_BRD0_Temperature': 0,  # CH0 - LTM4644_BRD0_temp
    'LTC2499_BRD1_Temperature': 1,  # CH1 - LTM4644_BRD1_temp
    'LTC2499_BRD2_Temperature': 2,  # CH2 - LTM4644_BRD2_temp
    'LTC2499_BRD3_Temperature': 3,  # CH3 - LTM4644_BRD3_temp
    'LTC2499_WIB1_Temperature': 4,  # CH4 - LTM4644_WIB1_temp
    'LTC2499_WIB2_Temperature': 5,  # CH5 - LTM4644_WIB2_temp
    'LTC2499_WIB3_Temperature': 6,  # CH6 - LTM4644_WIB3_temp
}


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
        receive_response(s)
        s.sendall((USERNAME + "\n").encode())
        receive_response(s)
        s.sendall((PASSWORD + "\n").encode())
        receive_response(s)
        s.sendall(b"\n")
        receive_response(s)
        print("Login successful.")
        return s
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


# ============================================================
# LTC2499 FUNCTIONS — matches C code read_ltc2499_temp()
# ============================================================

def ltc2499_c_style_voltage(raw_bytes, vref=2.578):
    """
    Convert LTC2499 raw 4 bytes to voltage.
    Matches C code: read_ltc2499_temp()

    C code reference:
        uint32_t value = bytes[3] | (bytes[2]<<8) | (bytes[1]<<16) | (bytes[0]<<24);
        double volts = ((value>>6) & 0x1FFFFFF)*1.25/pow(2,24);
        return ((volts > 1.25) ? volts-2*1.25 : volts) + 1.25;

    :param raw_bytes: List of 4 bytes [MSB, ..., LSB]
    :param vref: Reference voltage. Circuit: 3.3V*1K/(280+1K) ≈ 2.578V
    :return: Converted voltage (single-ended, COM-referenced)
    """
    if len(raw_bytes) != 4:
        raise ValueError(f"Expected 4 bytes, got {len(raw_bytes)}")

    # Build 32-bit value, big endian (MSB first)
    # C: bytes[3] | (bytes[2]<<8) | (bytes[1]<<16) | (bytes[0]<<24)
    value = (raw_bytes[0] << 24) | (raw_bytes[1] << 16) | (raw_bytes[2] << 8) | raw_bytes[3]

    # Extract 25-bit ADC code
    # C: (value>>6) & 0x1FFFFFF
    adc_code = (value >> 6) & 0x1FFFFFF

    # Scale to voltage using VREF/2
    # C: adc_code * 1.25 / pow(2,24)  (C hardcodes 1.25 = VREF/2 for VREF=2.5V)
    half_vref = vref / 2.0
    volts = adc_code * half_vref / (2 ** 24)

    # Bipolar wrap-around correction
    # C: (volts > 1.25) ? volts - 2*1.25 : volts
    if volts > half_vref:
        volts -= 2 * half_vref

    # Add COM offset (single-ended mode, COM = VREF/2)
    # C: + 1.25 /*COM*/
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
    """
    Compute first command byte for channel selection.
    Matches C: 0xB0 | ((ch%2)<<3) | (ch/2)
    """
    return 0xB0 | ((ch % 2) << 3) | (ch // 2)


def read_ltc2499_all_temperatures(connection, bus, addr, channels, vref=2.578):
    """
    Read all LTC2499 temperature channels using writeread (matches C i2c_writeread).
    Each read triggers the next channel conversion simultaneously.

    :param connection: Telnet socket
    :param bus: I2C bus number
    :param addr: LTC2499 I2C address
    :param channels: dict {sensor_name: channel_number}
    :param vref: Reference voltage
    :return: dict {sensor_name: temperature_celsius or None}
    """
    results = {}
    channel_list = list(channels.items())

    # Kickstart: write first channel to start first conversion
    first_ch = channel_list[0][1]
    byte0 = ltc2499_channel_byte(first_ch)
    send_command(connection, f'i2cset -y {bus} 0x{addr:02x} 0x{byte0:02x} 0x80')
    time.sleep(0.2)

    for i, (sensor_name, ch) in enumerate(channel_list):
        # Determine next channel (for pipelining)
        if i + 1 < len(channel_list):
            next_ch = channel_list[i + 1][1]
        else:
            next_ch = ch  # last channel: repeat same

        next_byte0 = ltc2499_channel_byte(next_ch)

        # writeread: write next channel select + read current result
        # Matches C: i2c_writeread(i2c, 0x15, cmd, 2, bytes, 4)
        temp_result = send_command(
            connection,
            f'i2ctransfer -y {bus} w2@0x{addr:02x} 0x{next_byte0:02x} 0x80 r4@0x{addr:02x}'
        )

        try:
            raw_bytes = parse_ltc2499_output(temp_result)
            print(f'    {sensor_name} raw: {[hex(b) for b in raw_bytes]}')
            volts = ltc2499_c_style_voltage(raw_bytes, vref=vref)
            temp_val = (0.598 - volts) / 0.002 + 27
            results[sensor_name] = temp_val
            print(f'    {sensor_name}: {temp_val:.2f} °C  (volts={volts:.4f}V)')
        except (ValueError, IndexError) as e:
            print(f'    \033[31m✗ {sensor_name}: Read FAILED ({e})\033[0m')
            results[sensor_name] = None

        time.sleep(0.2)

    return results


# ============================================================
# MAIN
# ============================================================

print("\033[35m" + "A_RT05_02 : I2C Sensor Information" + "\033[0m")
t1 = time.time()

time.sleep(2)
tcp = TCP_CFG()
udp = CLS_UDP()
conv = RAW_CONV()
now = datetime.now()

t1 = time.time()
psu = rigol.RigolDP800()

psu.set_channel(1, 12.0, 3.0, on=True)
psu.set_channel(2, 12.0, 3.0, on=True)
time.sleep(10)
v1, c1 = psu.measure(1)
v2, c2 = psu.measure(2)  # FIXED: was psu.measure(1)
time.sleep(1)
print('wait 30s')
time.sleep(30)  # wait for boot
print(c1)
print(c2)
ping_host(ip_address="192.168.121.1", count=4)
ping_host(ip_address="192.168.121.2", count=4)
time.sleep(1)
import component.temp as initial
initial
time.sleep(1)

connection = connect_to_server()
if connection:
    pass
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

# Read all 7 channels using corrected writeread method (matches C i2c_writeread)
ltc2499_results = read_ltc2499_all_temperatures(
    connection,
    bus=LTC2499_BUS,
    addr=LTC2499_ADDR,
    channels=LTC2499_CHANNELS,
    vref=LTC2499_VREF
)

# Store results into report dict
for sensor_name, temp_val in ltc2499_results.items():
    rp_dict.log04_wib[sensor_name] = temp_val

#########
tcp.tcp_poke(1, 0x05)
time.sleep(0.1)
readback = send_command(connection, 'i2cdetect -r -y 1')
print(readback)
Device = 'INA226';    Address = '46'
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
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
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
current_1 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V0.85_c'] = current_1
send_command(connection, 'i2cset -y 0 0x48 0x10')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_2 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V5.0_c'] = current_2
send_command(connection, 'i2cset -y 0 0x48 0x0A')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_3 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V1.8_c'] = current_3
send_command(connection, 'i2cset -y 0 0x48 0x14')
result = send_command(connection, 'i2ctransfer -y 0 r2@0x48')
msb, lsb = [int(x, 16) for x in result.splitlines()[1].split()]
raw = ((msb << 8) | lsb)
current_4 = ((((raw & 0x3fff)) * 0.000019075) / 0.1)
rp_dict.log04_wib['LTC2991_0x48_V2.5_c'] = current_4
send_command(connection, 'i2cset -y 0 0x48 0x01 0x00')
send_command(connection, 'i2cset -y 0 0x48 0x01 0x00')
send_command(connection, 'i2cset -y 0 0x48 0x0c')
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

time.sleep(0.5)
psu.safe_power_off()
psu.close()

import os

# === Setup relative path to ../report/wib_power_report_052.html ===
base_dir = os.path.dirname(os.path.abspath(__file__))
target_file_path = os.path.join(base_dir, "..", "report", "WIB_052_WIB_Power_report_052.html")
print(target_file_path)

# Ensure target directory exists
os.makedirs(os.path.dirname(target_file_path), exist_ok=True)

# Build table rows (handle None values gracefully)
rows = ""
for key, value in rp_dict.log04_wib.items():
    if value is not None:
        rows += f"<tr><td>{key}</td><td>{value:.3f}</td></tr>\n"
    else:
        rows += f"<tr><td>{key}</td><td style='color:red'>READ FAILED</td></tr>\n"

# HTML content with CSS styling
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WIB_052 WIB Power report</title>
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
    </style>
</head>
<body>
    <h2>WIB Power Report</h2>
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
</body>
</html>
"""

# Always create new file (overwrite if exists)
with open(target_file_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML report saved (new file) to {target_file_path}")