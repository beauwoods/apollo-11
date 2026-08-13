"""Popping calc, 1969.

The DSKY cannot draw a calculator.  Its entire renderable alphabet is blank
plus the ten digits, fixed in relay hardware
(PINBALL_GAME_BUTTONS_AND_LIGHTS.agc:378) -- the AGC emits 5-bit codes to a
decoder and never addresses segments.  A whole class of display-spoofing
attack is structurally impossible, by accident rather than design.

So instead of drawing one, we make the guidance computer *be* one: three
signed 5-digit registers showing operands and result.  Every value on the
display arrives by unauthenticated radio, including the flag that turns the
display on.
"""
import sys, os
BOOT_SETTLE = 10.0   # AGC fresh start must complete before it accepts input
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agc_link import AGC
from p27 import v72_write, verb, noun, load, enable_display

FAILREG = 0o0375          # three consecutive erasable words

A, B = 2, 2
RESULT = A + B

agc = AGC()
agc.pump(BOOT_SETTLE)

verb(agc, 37); load(agc, 0)          # P00
agc.pump(1.5)
enable_display(agc)
agc.pump(1.5)

print(f"=== uplinking operands and result: {A} + {B} = {RESULT} ===")
v72_write(agc, [
    (FAILREG + 0, A),
    (FAILREG + 1, B),
    (FAILREG + 2, RESULT),
])
agc.pump(2.0)

print("\n=== display three octal words (V05N09E) ===")
verb(agc, 5)
noun(agc, 9)
agc.pump(2.5)
print(agc.render())
print(f"\n   R1 = {A}   R2 = {B}   R3 = {RESULT}")
