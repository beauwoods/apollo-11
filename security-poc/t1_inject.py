"""Finding 1: the uplink is indistinguishable from the keyboard.

Run the identical keystroke sequence twice -- once as an astronaut
pressing keys (channel 015 -> KEYRUPT), once as an unauthenticated
radio transmission (channel 0173 -> INLINK -> UPRUPT) -- and compare
what the guidance computer displays.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BOOT_SETTLE = 10.0   # AGC fresh start must complete before it accepts input
from agc_link import AGC

SEQ = ["VERB", "3", "5", "ENTR"]      # V35E = lamp test

agc = AGC()
agc.pump(BOOT_SETTLE)
print("=== boot state ===")
print(agc.render())

print("\n=== via KEYBOARD (channel 015, KEYRUPT) ===")
for k in SEQ:
    agc.keypress(k)
    print(f"  after {k:5s}: PROG={agc.g(25)}{agc.g(24)} VERB={agc.g(23)}{agc.g(22)} NOUN={agc.g(21)}{agc.g(20)}")
print(agc.render())

# let the lamp test finish / reset
agc.keypress("RSET")
agc.pump(2.0)

print("\n=== via UPLINK (channel 0173, UPRUPT) -- no authentication ===")
for k in SEQ:
    agc.uplink(k)
    print(f"  after {k:5s}: PROG={agc.g(25)}{agc.g(24)} VERB={agc.g(23)}{agc.g(22)} NOUN={agc.g(21)}{agc.g(20)}")
print(agc.render())
