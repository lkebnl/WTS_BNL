# Test07 IBERT - Troubleshooting Guide

## Overview

This document describes the troubleshooting functionality added to the Test07_IBERT test script. The troubleshoot system provides:

- **Colored console output** for easy status identification
- **Detailed troubleshooting messages** with possible causes and actions
- **Validation functions** for power supply, Vivado execution, BER parsing, and eye scan
- **Test tracking** with pass/fail counts
- **Test summary** with overall status

## File Updated

| File | Description |
|------|-------------|
| `Test07_IBERT.py` | WIB Integrated Bit Error Ratio Test |

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
A_RT07: IBERT (Integrated Bit Error Ratio Test)
============================================================
  Initializing Power Supply...
  WIB Power - Ch1: 12.000V 1.500A, Ch2: 12.000V 1.200A

  Validating Power Supply...
  ✓ Ch1 Voltage PASS: 12.000V
  ✓ Ch1 Current PASS: 1.500A

============================================================
BER Results Parsing
============================================================
  Parsing Vivado output for BER data...
  ✓ X0Y4 BER data parsed successfully
      BER: 0.000000e+00
      ERROR_count: 000000000000
      BIT_count: 00003B9ACA00
```

---

## Troubleshooting Messages

The `TROUBLESHOOT` dictionary contains detailed guidance for 9 failure scenarios:

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

### 3. Vivado Execution Failed (`vivado_exec_fail`)

**When:** Vivado batch mode execution fails

```
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
```

### 4. TCL Script Execution Error (`tcl_script_fail`)

**When:** TCL script returns errors during execution

```
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
```

### 5. BER Results Parsing Failed (`ber_parse_fail`)

**When:** Cannot parse BER, ERROR_count, or BIT_count from Vivado output

```
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
```

### 6. X0Y4 Channel Bit Errors Detected (`x0y4_error_fail`)

**When:** MGT_X0Y4 channel has non-zero error count

```
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
```

### 7. X0Y5 Channel Bit Errors Detected (`x0y5_error_fail`)

**When:** MGT_X0Y5 channel has non-zero error count

```
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
```

### 8. Eye Scan Data Not Available (`eye_scan_fail`)

**When:** Eye scan CSV files not found or empty

```
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
```

### 9. Eye Scan Plot Generation Failed (`plot_gen_fail`)

**When:** Cannot generate eye scan PNG plot from CSV data

```
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

### `validate_vivado_execution(process, script_name, result_dict)`

Validates Vivado batch mode execution result.

**Parameters:**
- `process`: subprocess.run result object
- `script_name`: Name of TCL script that was executed
- `result_dict`: Dictionary to log errors

**Returns:** `True` if return code is 0, `False` otherwise

### `validate_ber_parsing(log07_ibert, channel, result_dict)`

Validates BER results were parsed for a specific channel.

**Parameters:**
- `log07_ibert`: Dictionary containing parsed BER data
- `channel`: Channel name (e.g., "X0Y4", "X0Y5")
- `result_dict`: Dictionary to log errors

**Returns:** `True` if all BER fields present, `False` otherwise

**Required Fields:**
- `{channel}_Total_BER`
- `{channel}_Total_ERROR_count`
- `{channel}_Total_BIT_count`

### `validate_channel_errors(error_count, channel, result_dict)`

Validates channel has zero bit errors.

**Parameters:**
- `error_count`: Integer error count (parsed from hex)
- `channel`: Channel name for logging
- `result_dict`: Dictionary to log errors

**Returns:** `True` if error_count is 0, `False` otherwise

### `validate_eye_scan_file(filepath, channel, result_dict)`

Validates eye scan CSV file exists.

**Parameters:**
- `filepath`: Full path to CSV file
- `channel`: Channel name for logging
- `result_dict`: Dictionary to log errors

**Returns:** `True` if file exists, `False` otherwise

---

## Test Sequence

| Test Phase | Description | Expected Result |
|------------|-------------|-----------------|
| Power Supply | Initialize and measure PSU | 12V ±1V, 0.5-3.0A |
| IBERT Init | Run initialization TCL script | Return code 0 |
| BER Accumulation | Wait 1000 seconds | Bits counted |
| BER Measurement | Run BER measurement TCL script | Return code 0 |
| BER Parsing | Parse Vivado output | X0Y4/X0Y5 data found |
| Error Evaluation | Check error counts | ERROR_count = 0 |
| Eye Scan | Run eye scan TCL script | Return code 0 |
| Eye Scan Files | Verify CSV files exist | scan00.csv, scan01.csv |
| Plot Generation | Generate BER heatmaps | PNG files created |

---

## MGT Channels Tested

| Channel | Description | Pass Criteria |
|---------|-------------|---------------|
| MGT_X0Y4 | GTX Transceiver Lane 4 | Total_ERROR_count = 0 |
| MGT_X0Y5 | GTX Transceiver Lane 5 | Total_ERROR_count = 0 |

---

## Integration Points

The troubleshoot functionality is integrated at these key points:

1. **Power Supply Initialization**
   - Validates voltage and current after power on
   - Shows `psu_voltage_fail` or `psu_current_fail` if out of range

2. **Vivado Script Execution**
   - Validates return code after each TCL script
   - Shows `vivado_exec_fail` if non-zero return
   - Shows `tcl_script_fail` if stderr contains ERROR

3. **BER Results Parsing**
   - Validates BER data for both channels
   - Shows `ber_parse_fail` if data missing

4. **Error Count Evaluation**
   - Validates error count is 0 for each channel
   - Shows `x0y4_error_fail` or `x0y5_error_fail` accordingly

5. **Eye Scan File Processing**
   - Validates CSV files exist
   - Shows `eye_scan_fail` if missing

6. **Plot Generation**
   - Try/except wrapper for matplotlib code
   - Shows `plot_gen_fail` on exception

7. **Test Summary**
   - Displays total tests passed vs failed
   - Lists all failed tests
   - Shows overall PASS/FAIL status

---

## Output Files Generated

| File | Description |
|------|-------------|
| `WIB_07_IBERT_report.html` | HTML report with status and eye scan images |
| `IBERT_test_results.csv` | CSV export of all test results |
| `scan00_X0Y4.csv` | Eye scan raw data for X0Y4 |
| `scan01_X0Y5.csv` | Eye scan raw data for X0Y5 |
| `eye_scan_X0Y4.png` | Eye scan BER heatmap for X0Y4 |
| `eye_scan_X0Y5.png` | Eye scan BER heatmap for X0Y5 |

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
| 2025-02-24 | Claude Code | Added troubleshoot functionality to Test07_IBERT |

