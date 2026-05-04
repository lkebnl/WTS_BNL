# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
import csv
import os

_WIB_INFO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file', 'wib_info.csv')
_DEFAULT_XILINX_PATH = "/home/dune/Vivado/Vivado/2022.2/bin/vivado"
_DEFAULT_LOCAL_PATH = 'D:/WIB_QC/DUNE_WIB_QC_Script'

def _read_wib_info(key, default):
    try:
        with open(_WIB_INFO_PATH, mode='r', newline='', encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) == 2 and row[0].strip() == key:
                    val = row[1].strip()
                    return val if val else default
    except Exception:
        pass
    return default

xilinx_path = _read_wib_info('XILINX_PATH', _DEFAULT_XILINX_PATH)
local_path   = _read_wib_info('LOCAL_PATH',  _DEFAULT_LOCAL_PATH)
