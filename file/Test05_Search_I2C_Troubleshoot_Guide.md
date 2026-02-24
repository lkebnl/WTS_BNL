# Test05 Search I2C - Troubleshooting Guide

## Overview

This document describes the troubleshooting functionality added to the Test05_Search_I2C test script. The troubleshoot system provides:

- **Colored console output** for easy status identification
- **Detailed troubleshooting messages** with possible causes and actions
- **Validation functions** for power supply, connection, and I2C device detection
- **I2C scan summary** with device count and failure list

## File Updated

| File | Description |
|------|-------------|
| `Test05_Search_I2C.py` | WIB I2C Device Search Test |

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
A_RT05_01 : Search I2C
============================================================
  Initializing Power Supply...
  WIB Power - Ch1: 12.000V 1.500A, Ch2: 12.000V 1.200A

  Validating Power Supply...
  ✓ Ch1 Voltage PASS: 12.000V
  ✓ Ch1 Current PASS: 1.500A
  ✓ Ch2 Voltage PASS: 12.000V
  ✓ Ch2 Current PASS: 1.200A

  [Bus 0x00] Scanning for SI5342...
    ✓ I2C Device SI5342 found at 0x6b
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

### 4. WIB Ping Failed (`ping_fail`)

**When:** WIB does not respond to ping

```
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
```

### 5. I2C Device Not Detected (`i2c_device_missing`)

**When:** Expected I2C device is not found at its address

```
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
```

### 6. TCP Poke Command Failed (`tcp_poke_fail`)

**When:** TCP register write to WIB fails

```
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
```

### 7. I2C Command Execution Failed (`i2c_command_fail`)

**When:** i2cdetect or i2cset command fails

```
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
```

### 8. WIB Login Failed (`login_fail`)

**When:** Telnet login credentials fail

```
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
- `device`: Device name (e.g., 'SI5342')
- `address`: Expected I2C address (e.g., '6b')
- `result_dict`: Dictionary to log errors

**Returns:** `True` if device found, `False` otherwise

### `validate_connection(connection, result_dict)`

Validates WIB Telnet connection.

**Parameters:**
- `connection`: Socket connection object
- `result_dict`: Dictionary to log errors

**Returns:** `True` if connected, `False` if None

### `retry_prompt(test_name)`

Prompts user for action on test failure.

**Parameters:**
- `test_name`: Name of the failed test

**Returns:** User choice:
- `'R'` - Retry the test
- `'S'` - Skip and continue
- `'E'` - Exit test

---

## I2C Devices Scanned

| Bus | I2C Bus | Device | Address |
|-----|---------|--------|---------|
| 0x00 | 0 | SI5342 | 0x6b |
| 0x01 | 0 | SI5344 | 0x6b |
| 0x02 | 0 | TCA9546ADR | 0x70 |
| 0x03 | 0 | LTC2991 | 0x48, 0x49, 0x4a, 0x4b |
| 0x03 | 0 | LTC2990 | 0x4e |
| 0x04 | 2 | TCA6424 | 0x22 |
| 0x04 | 2 | TCA642 | 0x23 |
| 0x05 | 1 | LTC2499 | 0x15 |
| 0x05 | 1 | INA226 | 0x46 |
| 0x05 | 1 | AD7414A | 0x49, 0x4a, 0x4d |
| 0x05 | 1 | SODIMM | 0x51 |
| 0x05 | 1 | LTC2991 | 0x48, 0x4c, 0x4e |
| 0x06 | 0 | DAC7574 | 0x4c, 0x4d, 0x4e, 0x4f |
| 0x07 | 0 | LTC2977 | 0x5c |
| 0x08 | 1 | DAC7574 | 0x4c, 0x4d |
| 0x09 | 0 | 24LC64SN | 0x50 |
| 0x0a | 0 | ADN2814 | 0x40 |

---

## Integration Points

The troubleshoot functionality is integrated at these key points:

1. **Power Supply Initialization**
   - Validates voltage and current after power on
   - Shows `psu_voltage_fail` or `psu_current_fail` if out of range

2. **WIB Connection**
   - Validates Telnet connection
   - Shows `connection_fail` if unable to connect

3. **I2C Bus Scanning**
   - Each device detection uses `validate_i2c_device()`
   - Tracks found/missing devices
   - Shows `i2c_device_missing` at end if any failures

4. **Test Summary**
   - Displays total devices found vs expected
   - Lists all missing devices
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
| 2025-02-24 | Claude Code | Added troubleshoot functionality to Test05_Search_I2C |

