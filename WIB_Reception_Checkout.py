# Developer  : lke, cde
# Email      : lingyun.lke@gmail.com
# Date       : April 2026
# Project    : DUNE WIB Quality Control System
# Institute  : BNL (Brookhaven National Laboratory)
# Repository : Public
# Copyright  : © 2026 Lingyun Ke. All rights reserved.
import subprocess

print("Reception Checkout Begin")
subprocess.run(["python", "./component/Test00_Reception_Checkout.py"])
print("Reception Checkout Done")
# import component.Test03_power_rail_for_FEMB as part03
# import component.Test07_IBERT as part07
