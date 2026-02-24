# Test052 Get Info From I2C - Troubleshooting Guide

## Overview

This document describes the troubleshooting functionality added to the Test052_getInfoFromI2C test script. The troubleshoot system provides:

- **Colored console output** for easy status identification
- **Detailed troubleshooting messages** with possible causes and actions
- **Validation functions** for power supply, I2C devices, temperature, and voltage readings
- **Sensor read tracking** with success/failure counts
- **Test summary** with overall status

## File Updated

| File | Description |
|------|-------------|
| `Test052_getInfoFromI2C.py` | WIB I2C Sensor Information Test |

---

## Helper Functions

### Console Output Functions

```python
print_header(msg)   # Purple header with "=" separator lines
print_pass(msg)     # Green text for success messages
print_fail(msg)     # Red text for failure messages
print_warning(msg)  # Yellow text for warnings
print_info(msg)     # Cyan text for information
```

### Example Output

```
============================================================
A_RT05_02 : I2C Sensor Information
============================================================
  Initializing Power Supply...
  WIB Power - Ch1: 12.000V 1.500A, Ch2: 12.000V 1.200A

  Validating Power Supply...
  ✓ Ch1 Voltage PASS: 12.000V
  ✓ Ch1 Current PASS: 1.500A

  [LTC2499] Reading Temperature Sensors...
    ✓ I2C Sensor LTC2499 found at 0x15
    ✓ LTC2499_BRD0_Temperature: 25.50°C
    ✓ LTC2499_BRD1_Temperature: 26.20°C
```

---

## Troubleshooting Messages

The `TROUBLESHOOT` dictionary contains detailed guidance for 8 failure scenarios:

### 1. WIB Connection Failed (`connection_fail`)

**When:** Telnet connection to WIB fails

```
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
```

### 2. Power Supply Voltage Out of Range (`psu_voltage_fail`)

**When:** PSU voltage measurement is outside 11.0-13.0V range

```
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
```

### 3. Power Supply Current Abnormal (`psu_current_fail`)

**When:** PSU current is outside 0.5-3.0A range

```
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
```

### 4. I2C Sensor Not Detected (`i2c_device_missing`)

**When:** Expected I2C sensor is not found at its address

```
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
```

### 5. Sensor Read Failed (`sensor_read_fail`)

**When:** Sensor data read operation fails

```
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
```

### 6. Temperature Reading Out of Range (`temperature_out_of_range`)

**When:** Temperature reading is outside -10°C to 85°C range

```
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
```

### 7. Voltage Reading Out of Range (`voltage_out_of_range`)

**When:** Voltage reading is outside expected tolerance

```
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
```

### 8. Current Reading Out of Range (`current_out_of_range`)

**When:** Current reading is outside expected limits

```
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
```

---

## Validation Functions

### `validate_power_supply(v1, c1, v2, c2, result_dict)`

Validates power supply voltage and current readings.

**Parameters:**
- `v1`, `c1`: Channel 1 voltage and current
- `v2`, `c2`: Channel 2 voltage and current
- `result_dict`: Dictionary to log errors

**Returns:** `True` if all readings within range, `False` otherwise

**Ranges:**
- Voltage: 11.0V - 13.0V (for 12V supply)
- Current: 0.5A - 3.0A

### `validate_i2c_device(readback, device, address, result_dict)`

Validates I2C device detection from i2cdetect output.

**Parameters:**
- `readback`: Output from i2cdetect command
- `device`: Device name (e.g., 'LTC2499')
- `address`: Expected I2C address (e.g., '15')
- `result_dict`: Dictionary to log errors

**Returns:** `True` if device found, `False` otherwise

### `validate_temperature(value, sensor_name, min_temp, max_temp, result_dict)`

Validates temperature reading is within expected range.

**Parameters:**
- `value`: Temperature value in °C
- `sensor_name`: Name of the sensor
- `min_temp`: Minimum acceptable temperature (default -10°C)
- `max_temp`: Maximum acceptable temperature (default 85°C)
- `result_dict`: Dictionary to log errors

**Returns:** `True` if within range, `False` otherwise

### `validate_voltage(value, sensor_name, nominal, tolerance_pct, result_dict)`

Validates voltage reading is within tolerance of nominal.

**Parameters:**
- `value`: Voltage value
- `sensor_name`: Name of the sensor
- `nominal`: Expected nominal voltage
- `tolerance_pct`: Tolerance percentage (default 10%)
- `result_dict`: Dictionary to log errors

**Returns:** `True` if within tolerance, `False` otherwise

### `validate_connection(connection, result_dict)`

Validates WIB Telnet connection.

**Parameters:**
- `connection`: Socket connection object
- `result_dict`: Dictionary to log errors

**Returns:** `True` if connected, `False` if None

---

## I2C Sensors Read

| Sensor | Address | Measurements |
|--------|---------|--------------|
| LTC2499 | 0x15 | BRD0-3 Temperature, WIB1-3 Temperature |
| INA226 | 0x46 | Vbus Voltage, Current |
| AD7414 | 0x49, 0x4a, 0x4d | Temperature |
| LTC2991 | 0x48 | Temperature, V0.85, V5.0, V2.5, V1.8 (V & I), VCC |
| LTC2990 | 0x4c | Temperature, V1.2, V3.3, VCC, Current |
| LTC2990 | 0x4e | Temperature, V0.9, VCCPSPLL_1.2, PSDDR4, VCC, Current |

---

## Integration Points

The troubleshoot functionality is integrated at these key points:

1. **Power Supply Initialization**
   - Validates voltage and current after power on
   - Shows `psu_voltage_fail` or `psu_current_fail` if out of range

2. **WIB Connection**
   - Validates Telnet connection
   - Shows `connection_fail` if unable to connect

3. **I2C Sensor Detection**
   - Each sensor detection uses `validate_i2c_device()`
   - Shows `i2c_device_missing` if sensor not found

4. **Temperature Reading**
   - Uses `validate_temperature()` with range checking
   - Tracks success/failure counts

5. **Test Summary**
   - Displays total sensors read vs failed
   - Lists all failed sensors/devices
   - Shows overall PASS/FAIL status

---

## Color Codes Reference

| Color | ANSI Code | Usage |
|-------|-----------|-------|
| Purple | `\033[35m` | Headers, section titles |
| Green | `\033[32m` | Pass messages, success |
| Red | `\033[31m` | Fail messages, errors |
| Yellow | `\033[33m` | Warnings, cautions |
| Cyan | `\033[36m` | Information messages |
| Reset | `\033[0m` | Return to default |

---

## Version History

| Date | Author | Description |
|------|--------|-------------|
| 2025-02-24 | Claude Code | Added troubleshoot functionality to Test052_getInfoFromI2C |

