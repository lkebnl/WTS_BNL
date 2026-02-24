# Test040x FEMB Pulse Test - Troubleshooting Guide

## Overview

This document describes the troubleshooting functionality added to the Test040x WIB FEMB Pulse test scripts. The troubleshoot system provides:

- **Colored console output** for easy status identification
- **Detailed troubleshooting messages** with possible causes and actions
- **Validation functions** for power modes and ASIC data
- **User interaction options** for retry/skip/exit on failures

## Files Updated

| File | FEMB Slot | Report Key |
|------|-----------|------------|
| `Test0400_WIB_FEMB_Pulse.py` | Slot 0 | item041 |
| `Test0401_WIB_FEMB_Pulse.py` | Slot 1 | item042 |
| `Test0402_WIB_FEMB_Pulse.py` | Slot 2 | item043 |
| `Test0403_WIB_FEMB_Pulse.py` | Slot 3 | item044 |

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
A_RT03_01 : Power Rail
============================================================
  ✓ SEOFF Mode Power Check PASSED
  ✓ SEON Mode Power Check PASSED
  ✓ DIFF Mode Power Check PASSED
    ✓ ASIC 0 data acquired successfully
    ✓ ASIC 1 data acquired successfully
```

---

## Troubleshooting Messages

The `TROUBLESHOOT` dictionary contains detailed guidance for 9 failure scenarios:

### 1. WIB Service Restart Failed (`wib_service_fail`)

**When:** WIB service restart fails after 5 retry attempts

```
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
```

### 2. SEOFF Mode Power Check Failed (`seoff_power_fail`)

**When:** Power check fails during SEOFF (Single-Ended OFF) mode test

```
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
```

### 3. SEON (SDC) Mode Power Check Failed (`seon_power_fail`)

**When:** Power check fails during SEON (Single-Ended ON / SDC) mode test

```
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
```

### 4. DIFF Mode Power Check Failed (`diff_power_fail`)

**When:** Power check fails during Differential mode test

```
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
```

### 5. UDP Data Acquisition Failed (`udp_data_fail`)

**When:** UDP data stream fails to deliver packets

```
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
```

### 6. ASIC Data Readout Failed (`asic_readout_fail`)

**When:** ASIC returns no data (chip_data is None)

```
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
```

### 7. TCP Communication Failed (`tcp_link_fail`)

**When:** TCP connection to WIB fails

```
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
```

### 8. FEMB Voltage Out of Range (`femb_voltage_fail`)

**When:** Measured FEMB voltage exceeds tolerance

```
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
```

### 9. FEMB Current Too High (`femb_current_high`)

**When:** Measured FEMB current exceeds safe limits

```
┌─────────────────────────────────────────────────────────────┐
│  WARNING: FEMB CURRENT TOO HIGH                             │
├─────────────────────────────────────────────────────────────┤
│  Possible Causes:                                           │
│  • Short circuit on FEMB                                    │
│  • Component failure                                        │
│  • Excessive ASIC activity                                  │
│  • Thermal runaway condition                                │
│                                                             │
│  CAUTION: High current may indicate fault!                  │
│                                                             │
│  Actions:                                                   │
│  1. Power off FEMB slot immediately                         │
│  2. Allow FEMB to cool down                                 │
│  3. Inspect for visible damage or burns                     │
│  4. Check for solder bridges or debris                      │
│  5. Do not retry without thorough inspection                │
└─────────────────────────────────────────────────────────────┘
```

---

## Validation Functions

### `validate_power_mode(mode_name, pwr_en, detailed_checks)`

Validates power mode test results and displays troubleshooting on failure.

**Parameters:**
- `mode_name`: "SEOFF", "SEON", or "DIFF"
- `pwr_en`: Power enable status (0 = fail, 1 = pass)
- `detailed_checks`: Dictionary with rail check results

**Returns:** `True` if passed, `False` if failed

**Example:**
```python
pwr_en, detailed_checks = chkout_top.pwr_chk(pwr_info, v_fe, v_adc, v_cd, v_bias, ...)
seoff_ok = validate_power_mode("SEOFF", pwr_en, detailed_checks)
```

### `validate_asic_data(chip_data, asic_num)`

Validates ASIC data readout and displays troubleshooting on failure.

**Parameters:**
- `chip_data`: Data returned from ASIC readout (None if failed)
- `asic_num`: ASIC number (0-7)

**Returns:** `True` if data valid, `False` if None

### `retry_prompt(test_name)`

Prompts user for action on test failure.

**Parameters:**
- `test_name`: Name of the failed test

**Returns:** User choice:
- `'R'` - Retry the test
- `'S'` - Skip and continue
- `'E'` - Exit test

---

## Integration Points

The troubleshoot functionality is integrated at these key points:

1. **WIB Service Restart** (`safe_restart_wib_service()`)
   - Shows `wib_service_fail` after 5 failed retry attempts

2. **SEOFF Mode Test**
   - Calls `validate_power_mode("SEOFF", ...)` after power check
   - Logs errors to `result_dict["error_log"]`

3. **SEON Mode Test**
   - Calls `validate_power_mode("SEON", ...)` after power check
   - Logs errors to `result_dict["error_log"]`

4. **DIFF Mode Test**
   - Calls `validate_power_mode("DIFF", ...)` after power check
   - Logs errors to `result_dict["error_log"]`

5. **ASIC Data Acquisition**
   - Shows success/failure message for each ASIC (0-7)
   - Shows `asic_readout_fail` if chip_data is None

---

## Related Files

- `Test03_power_rail_for_FEMB_1V.py` - Similar troubleshoot for power rail tests
- `Test03_power_rail_for_FEMB_2V.py` - Similar troubleshoot for power rail tests
- `Test03_power_rail_for_FEMB_3V.py` - Similar troubleshoot for power rail tests
- `Test03_power_rail_for_FEMB_4V.py` - Similar troubleshoot for power rail tests

---


