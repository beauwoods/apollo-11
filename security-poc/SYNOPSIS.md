# Apollo 11 AGC — Security Audit Synopsis

**Task:** review the Apollo 11 guidance computer source for security vulnerabilities.
**Scope:** 130,186 lines of 1969 AGC assembly (Comanche055 / CM, Luminary099 / LM), plus the repo's modern CI.
**Result:** four findings in the flight software, all demonstrated in an emulator; one live vulnerability in the repo's GitHub Actions.

---

## The core finding

The AGC had a **remote command path with no authentication of any kind.**

`UPRUPT` takes a word off the S-band radio uplink, checks only that it is formatted
as `[char][~char][char]` — a repetition code against radio noise, with no key and a
published layout — and then jumps to `ACCEPTUP`, **the same handler a physical
keystroke reaches**. To the computer, a radio transmission and an astronaut's finger
are the same event.

From there, P27's V72 "scatter update" takes an uplinked address straight into the
`EBANK` register and stores to it. No allow-list, no range check.

The defenses were real but entirely physical: Deep Space Network antenna
directionality, link budget, and a switch on the crew panel.

---

## Findings

| # | Finding | Status |
|---|---------|--------|
| 1 | Uplink is indistinguishable from the keyboard (`KEYRUPT_UPRUPT.agc:65-105`) | Demonstrated |
| 2 | Uplinked memory write has no destination validation (`UPDATE_PROGRAM.agc:459-476`) | Demonstrated |
| 3 | Uplink lockout is a DoS vector and self-unlocking via unauthenticated ERROR RESET | Demonstrated |
| 4 | `UPRUPT` skips `KEYCOM`, so uplinked commands never set the display-enable flag | Demonstrated |
| 5 | CI uses `paulfantom/periodic-labeler@master` — unpinned third-party action with a write-capable token | **Live today** |
| — | Arbitrary code execution via `LST2` WAITLIST pointers (18 words of erasable) | **Unverified** |

Finding 5 is the only one that is actionable now. Fix: pin to a commit SHA, add a
least-privilege `permissions:` block.

---

## What was demonstrated

Built the Virtual AGC toolchain, assembled the real Comanche055 rope, and drove the
emulated computer over yaAGC's uplink channel — the emulator's model of the S-band
up-data link. Captured output in `results.txt`; all four reproduce from a cold boot.

**The headline run — pure radio, no key ever pressed:**

```
R1  01202     <- fabricated alarm, written from the ground
R2  00000
R3  00000
```

The attacker enters P00, switches the crew's display on by writing `DSKYFLAG`, writes
`01202` into `FAILREG`, then uplinks V05N09E — the same keystrokes the crew used on
20 July 1969 — to read it back. The executive was never loaded. The alarm is invention.

**A detail worth the whole exercise:** the "before" read showed `01107` — PHASE TABLE
ERROR. That one is *real*, the computer catching its own cold start when the
phase-table complement check fails. A genuine self-detected alarm and a forged one
render identically on the panel.

---

## The other half: this is exceptionally resilient software

Auditing for weaknesses surfaced how much of the design is deliberately fail-safe:

- **Restart is routine, not exceptional.** Recovery is declarative data in restart
  tables, not scattered exception handlers.
- **Recovery metadata is verified before it is trusted.** Every phase is stored twice,
  direct and complemented, XOR'd on restart; mismatch means alarm 1107 and a full
  fresh start rather than resuming from state it can't trust.
- **Critical actuator state survives the reboot.** A restart mid-burn re-asserts the
  engine-on discrete before anything else.
- **Graceful degradation by priority.** Resource exhaustion sheds low-priority work
  and keeps flying — the 1201/1202 behavior that saved the actual landing.
- **Self-test on spare cycles only.** Runs at zero priority with no core set, yielding
  to any real job between every step.
- **Diagnostics preserve root cause.** `FAILREG` keeps the *first* three alarms and
  flags overflow rather than overwriting.
- **The display can't be drawn on.** Its entire alphabet is blank plus ten digits,
  fixed in relay hardware — a whole class of UI-spoofing attack is structurally
  impossible. Accidental, but real.

The same machine with zero authentication on its command link verifies its own
recovery metadata before trusting it. They weren't sloppy — they solved the threat
model they actually had: radio noise and hardware faults, not adversaries.

---

## Scope limits

- Shows the **software** accepted unauthenticated commands. Does **not** show the real
  system was exploitable.
- The emulator has no RF model. The real Up-Data Link applied its own vehicle address
  and encoding **upstream** of `UPRUPT` — the triple-redundancy check is the AGC's last
  line, not the first. Whether the end-to-end radio path was injectable is unresolved.
- Historical research only. No AGC has flown since 1972; the source is public domain.

---

## Context

No published security analysis of the AGC flight code appears to exist. The most
rigorous recent work — JUXT's 2026 discovery of an `LGYRO` resource-lock leak, which
we independently re-derived from source — reported finding no prior formal
verification, model checking, or static analysis against it.

A widely repeated claim that the AGC had "no remote way to send commands" is simply
false, and the hardware community has independently confirmed it: Ken Shirriff's team
restored an Apollo **Up-Data Link Confidence Test Set** to working order in 2025, and
describes Mission Control as having controlled the computer "keypress by keypress."

**Testing on original hardware is feasible.** One operational AGC exists (privately
owned, restored 2019), alongside a working UDL test set and restored S-band equipment
— all in private and hobbyist hands, not NASA or the Smithsonian, whose units are
static museum artifacts.

---

**Artifact:** simulated DSKY replaying all four runs — https://claude.ai/code/artifact/5775f87d-2598-4cdf-a90e-a68ad32e74be
**Code:** `security-poc/` on branch `claude/apollo-11-security-audit-bniywp`
