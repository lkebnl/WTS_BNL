# Test06 PTB Interface Path - Troubleshooting Guide

## Overview

This document describes the troubleshooting functionality added to the Test06_PTB_Interface_Path test script. The troubleshoot system provides:

- **Colored console output** for easy status identification
- **Detailed troubleshooting messages** with possible causes and actions
- **Validation functions** for power supply, network, clock chips, and interfaces
- **Test tracking** with pass/fail counts
- **Test summary** with overall status

## File Updated

| File | Description |
|------|-------------|
| `Test06_PTB_Interface_Path.py` | WIB PTB Interface Path Test |

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
A_RT06: PTB Interface Path
============================================================
  Initializing Power Supply...
  WIB Power - Ch1: 12.000V 1.500A, Ch2: 12.000V 1.200A

  Validating Power Supply...
  ✓ Ch1 Voltage PASS: 12.000V
  ✓ Ch1 Current PASS: 1.500A

============================================================
Clock Chip Detection Test
============================================================
  Testing SI5342 Clock Chip...
  ✓ SI5342 detected (0x42)
  Testing SI5344 Clock Chip...
  ✓ SI5344 detected (0x44)
```

---

## Troubleshooting Messages

The `TROUBLESHOOT` dictionary contains detailed guidance for 8 failure scenarios:

### 1. Power Supply Voltage Out of Range (`psu_voltage_fail`)

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

### 2. Power Supply Current Abnormal (`psu_current_fail`)

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

### 3. WIB Ping Failed (`ping_fail`)

**When:** WIB does not respond to ping

```
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: WIB PING FAILED                              │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB not fully booted (need ~60s after power on)          │
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

### 4. SI5342 Clock Chip Not Detected (`si5342_fail`)

**When:** SI5342 clock chip ID read fails (expected 0x42)

```
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: SI5342 CLOCK CHIP NOT DETECTED               │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • SI5342 chip not properly soldered                        │
│  • I2C bus multiplexer not configured                       │
│  • Clock chip power supply issue                            │
│  • I2C communication error                                  │
│                                                             │
│  Actions:                                                   │
│  1. Check SI5342 power rail voltage                         │
│  2. Verify I2C bus configuration (tcp.tcp_poke(1, 0x01))    │
│  3. Check for cold solder joints on SI5342                  │
│  4. Measure I2C clock and data signals                      │
│  5. Try resetting I2C bus and retry                         │
└─────────────────────────────────────────────────────────────┘
```

### 5. SI5344 Clock Chip Not Detected (`si5344_fail`)

**When:** SI5344 clock chip ID read fails (expected 0x44)

```
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: SI5344 CLOCK CHIP NOT DETECTED               │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • SI5344 chip not properly soldered                        │
│  • I2C bus multiplexer not configured                       │
│  • Clock chip power supply issue                            │
│  • Previous SI5342 test affected bus state                  │
│                                                             │
│  Actions:                                                   │
│  1. Check SI5344 power rail voltage                         │
│  2. Verify I2C bus configuration (tcp.tcp_poke(1, 0x00))    │
│  3. Check for cold solder joints on SI5344                  │
│  4. Reset I2C bus before retry                              │
│  5. Check clock input signals to SI5344                     │
└─────────────────────────────────────────────────────────────┘
```

### 6. FP/BK Interface Test Failed (`fp_bk_fail`)

**When:** FP/BK interface register read fails (expected 0x60000000)

```
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: FP/BK INTERFACE TEST FAILED                  │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Front panel / backplane connector issue                  │
│  • FPGA configuration not loaded correctly                  │
│  • Signal integrity problem on interface                    │
│  • SI5344 clock not properly configured                     │
│                                                             │
│  Expected Value: 0x60000000                                 │
│                                                             │
│  Actions:                                                   │
│  1. Check front panel connector seating                     │
│  2. Verify SI5344 configuration completed                   │
│  3. Check FPGA status register                              │
│  4. Inspect FP/BK interface signals with scope              │
│  5. Try power cycling and reconfiguring                     │
└─────────────────────────────────────────────────────────────┘
```

### 7. TCP Communication Failed (`tcp_comm_fail`)

**When:** TCP communication to WIB fails

```
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: TCP COMMUNICATION FAILED                     │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • WIB TCP server not responding                            │
│  • Network connection interrupted                           │
│  • WIB firmware issue                                       │
│  • Register address invalid                                 │
│                                                             │
│  Actions:                                                   │
│  1. Verify WIB is still reachable (ping test)               │
│  2. Check TCP port connectivity                             │
│  3. Power cycle WIB and retry                               │
│  4. Check WIB firmware version                              │
│  5. Monitor WIB serial console for errors                   │
└─────────────────────────────────────────────────────────────┘
```

### 8. LEMO Interface Test Failed (`lemo_test_fail`)

**When:** LEMO connector interface test fails

```
┌─────────────────────────────────────────────────────────────┐
│  TROUBLESHOOT: LEMO INTERFACE TEST FAILED                   │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • LEMO connector not properly connected                    │
│  • Signal routing issue on board                            │
│  • FPGA I/O configuration error                             │
│  • External loopback cable missing                          │
│                                                             │
│  Actions:                                                   │
│  1. Check LEMO connector connections                        │
│  2. Verify loopback cable is installed                      │
│  3. Check FPGA pin configuration                            │
│  4. Measure signals at LEMO connectors                      │
│  5. Verify board assembly near LEMO connectors              │
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

### `validate_ping(ping_result, ip_address, result_dict)`

Validates ping test result.

**Parameters:**
- `ping_result`: Boolean result from ping_host()
- `ip_address`: IP address that was pinged
- `result_dict`: Dictionary to log errors

**Returns:** `True` if ping succeeded, `False` otherwise

### `validate_clock_chip(chip_value, expected_value, chip_name, result_dict)`

Validates clock chip detection via I2C.

**Parameters:**
- `chip_value`: Value read from clock chip
- `expected_value`: Expected chip ID (0x42 for SI5342, 0x44 for SI5344)
- `chip_name`: Name of the chip for logging
- `result_dict`: Dictionary to log errors

**Returns:** `True` if chip detected correctly, `False` otherwise

### `validate_fp_bk_interface(value, expected_value, result_dict)`

Validates FP/BK interface test.

**Parameters:**
- `value`: Value read from interface register
- `expected_value`: Expected value (0x60000000)
- `result_dict`: Dictionary to log errors

**Returns:** `True` if interface active, `False` otherwise

---

## Test Sequence

| Test Phase | Description | Expected Result |
|------------|-------------|-----------------|
| Power Supply | Initialize and measure PSU | 12V ±1V, 0.5-3.0A |
| Network | Ping WIB IP addresses | 192.168.121.1 and .2 respond |
| LEMO | Test LEMO connectors | Loopback verified |
| I2C PTC | Test I2C PTC interface | Register read/write |
| SI5342 | Detect SI5342 clock chip | ID = 0x42 |
| SI5344 | Detect and configure SI5344 | ID = 0x44 |
| FP/BK | Test front panel/backplane | Register = 0x60000000 |

---

## Integration Points

The troubleshoot functionality is integrated at these key points:

1. **Power Supply Initialization**
   - Validates voltage and current after power on
   - Shows `psu_voltage_fail` or `psu_current_fail` if out of range

2. **Network Connectivity**
   - Validates ping to both WIB IP addresses
   - Shows `ping_fail` if unreachable

3. **Clock Chip Detection**
   - Validates SI5342 chip ID (0x42)
   - Validates SI5344 chip ID (0x44)
   - Shows respective troubleshoot on failure

4. **FP/BK Interface**
   - Validates interface register value
   - Shows `fp_bk_fail` if not 0x60000000

5. **Test Summary**
   - Displays total tests passed vs failed
   - Lists all failed tests
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
| 2025-02-24 | Claude Code | Added troubleshoot functionality to Test06_PTB_Interface_Path |

