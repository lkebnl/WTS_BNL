#!/usr/bin/env python3
"""
WIB QC Cycle Test Runner
Select one or more test items and run them for N cycles.
Run from the WTS_BNL directory: python3 cycle_test.py
"""

import subprocess
import sys
import os
import time
from datetime import datetime

_PY   = sys.executable
_BASE = os.path.dirname(os.path.abspath(__file__))

TESTS = [
    ( 1, "QSPI Item 0101",                    "component/item0101_QSPI.py"),
    ( 2, "QSPI Item 0102",                    "component/item0102_QSPI.py"),
    ( 3, "Test01  Serial / TCPIP Comm",       "component/Test01_Serial_TCPIP_Communication.py"),
    ( 4, "Test02  Calibration Path Control",  "component/Test02_Calibration_Path_Control.py"),
    ( 5, "Test03  Power Rail FEMB Slot0 1V",  "component/Test03_power_rail_for_FEMB_1V.py"),
    ( 6, "Test03  Power Rail FEMB Slot1 2V",  "component/Test03_power_rail_for_FEMB_2V.py"),
    ( 7, "Test03  Power Rail FEMB Slot2 3V",  "component/Test03_power_rail_for_FEMB_3V.py"),
    ( 8, "Test03  Power Rail FEMB Slot3 4V",  "component/Test03_power_rail_for_FEMB_4V.py"),
    ( 9, "Test0400 WIB FEMB Pulse Slot0",     "component/Test0400_WIB_FEMB_Pulse.py"),
    (10, "Test0401 WIB FEMB Pulse Slot1",     "component/Test0401_WIB_FEMB_Pulse.py"),
    (11, "Test0402 WIB FEMB Pulse Slot2",     "component/Test0402_WIB_FEMB_Pulse.py"),
    (12, "Test0403 WIB FEMB Pulse Slot3",     "component/Test0403_WIB_FEMB_Pulse.py"),
    (13, "Test05   Search I2C",               "component/Test05_Search_I2C.py"),
    (14, "Test052  I2C Sensor Info",          "component/Test052_getInfoFromI2C.py"),
    (15, "Test06   PTB Interface Path",       "component/Test06_PTB_Interface_Path.py"),
    (16, "Test07   IBERT",                    "component/Test07_IBERT.py"),
    (17, "Test0803 CTS Checkout",             "component/Test0803_CTS_Checkout.py"),
]

# ── colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def _c(text, colour): return f"{colour}{text}{RESET}"


# ── UI helpers ─────────────────────────────────────────────────────────────────
def print_menu():
    print("\n" + "="*62)
    print(_c("  WIB QC  —  Cycle Test Runner", BOLD))
    print("="*62)
    print(f"  {'No.':<5}  Test Item")
    print("-"*62)
    for num, name, _ in TESTS:
        print(f"  {num:<5}  {name}")
    print("-"*62)
    print("  Enter item numbers separated by commas  e.g.  1,3,14")
    print("  Type  all  to select every test")
    print("="*62)


def get_selection():
    while True:
        raw = input("\nSelect items: ").strip()
        if raw.lower() == "all":
            return [num for num, _, _ in TESTS]
        try:
            nums   = [int(x.strip()) for x in raw.split(",") if x.strip()]
            valid  = {t[0] for t in TESTS}
            bad    = [n for n in nums if n not in valid]
            if bad:
                print(f"  Unknown item(s): {bad}. Valid range 1-{len(TESTS)}")
                continue
            if not nums:
                print("  No items entered.")
                continue
            return list(dict.fromkeys(nums))          # deduplicate, keep order
        except ValueError:
            print("  Invalid input — enter numbers like  1,3,5  or  all")


def get_cycles():
    while True:
        raw = input("Number of cycles : ").strip()
        try:
            n = int(raw)
            if n >= 1:
                return n
        except ValueError:
            pass
        print("  Please enter a positive integer.")


# ── test runner ────────────────────────────────────────────────────────────────
def run_test(script_rel_path) -> bool:
    full_path = os.path.join(_BASE, script_rel_path)
    if not os.path.exists(full_path):
        print(_c(f"  [ERROR] Script not found: {full_path}", RED))
        return False
    result = subprocess.run([_PY, full_path], cwd=_BASE)
    return result.returncode == 0


# ── summary ────────────────────────────────────────────────────────────────────
def print_summary(selected_nums, results, total_cycles):
    name_map   = {num: name for num, name, _ in TESTS}
    all_passed = True

    print("\n" + "="*70)
    print(_c("  CYCLE TEST SUMMARY", BOLD))
    print("="*70)
    print(f"  {'#':<5}  {'Test Item':<38}  {'PASS':>5}  {'FAIL':>5}  {'Result'}")
    print("-"*70)
    for num in selected_nums:
        passes = sum(results[num])
        fails  = total_cycles - passes
        if fails:
            all_passed = False
        verdict = _c("PASS", GREEN) if fails == 0 else _c("FAIL", RED)
        print(f"  {num:<5}  {name_map[num]:<38}  {passes:>5}  {fails:>5}  {verdict}")
    print("-"*70)

    overall = _c("ALL PASS", GREEN) if all_passed else _c("HAS FAILURES", RED)
    print(f"  Overall : {overall}")
    print(f"  Cycles  : {total_cycles}")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    print_menu()
    selected_nums = get_selection()
    cycles        = get_cycles()

    name_map = {num: name for num, name, _ in TESTS}
    path_map = {num: path for num, _, path in TESTS}

    print(f"\n  {len(selected_nums)} test(s) selected  |  {cycles} cycle(s)")
    print(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print("  Tests to run:")
    for num in selected_nums:
        print(f"    [{num}] {name_map[num]}")

    results = {num: [] for num in selected_nums}

    for cycle in range(1, cycles + 1):
        print(f"\n{'='*62}")
        print(_c(f"  CYCLE  {cycle} / {cycles}", BOLD))
        print("="*62)

        for num in selected_nums:
            name = name_map[num]
            print(f"\n  [{cycle}/{cycles}]  {name}")
            print(f"  {'─'*56}")
            t0     = time.time()
            passed = run_test(path_map[num])
            elapsed = time.time() - t0
            verdict = _c("PASS", GREEN) if passed else _c("FAIL", RED)
            print(f"\n  Result: {verdict}   ({elapsed:.1f} s)")
            results[num].append(passed)

        # per-cycle mini summary
        cycle_pass = all(results[num][-1] for num in selected_nums)
        print(f"\n  Cycle {cycle} overall: {_c('PASS', GREEN) if cycle_pass else _c('FAIL', RED)}")

    print_summary(selected_nums, results, cycles)


if __name__ == "__main__":
    main()
