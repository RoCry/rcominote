# Exact-model radio evidence

2026-10-13. New exact-model lead, not an official certificate acquisition.
Owner clarified that Wi-Fi was inferred from other recorders, not promised on
a known CoMi product page. [Source digest/fields](evidence/wifi-radio-model-2026-10-13.json).

The [third-party CMIIT index](https://cmiitid.cn/2026-6996) reports the exact
manual model **SY-N2A3F-5H2**, applicant **北京致远互联软件股份有限公司**:

| Reported field | Value |
|---|---|
| Equipment / technical module | 蓝牙设备 / 蓝牙 |
| Approval number / code | 2026-6996 / 26J11X2GE501 |
| Issue date | 2026-04-15 |
| Modulation | GFSK, π/4-DQPSK, 8DPSK |
| Occupied bandwidth | ≤2 MHz |
| Frequency | 2400–2483.5 MHz |

This is model-specific Bluetooth evidence, stronger than similarity to another
recorder's SDK. The page's separate generic frequency-band description mentions
“WIFI/WLAN/BT”; it describes shared spectrum use, **not Wi-Fi support in this
model**. Do not turn that section into a positive Wi-Fi claim.

Primary verification attempted through the [MIIT result-query page](https://ythzxfw.miit.gov.cn/jgcx/index.html):
localwebrs returned the page heading; direct curl returned403. Chrome loaded
the official form, but business-category/results data did not populate; entering
the exact model and submitting produced no result record. One console Axios
error was observed. This is an unsuccessful query, not a regulator “no records”
response. No CAPTCHA, account or bypass attempted.

## Decision and remaining evidence

Combined with the manual's Bluetooth-only instructions, ATS3085L's documented
Bluetooth platform, actual Boyi rejection of related Wi-Fi opcodes and the
unconnected Wi-Fi-named UI, this supports **working on the assumption that
the current CoMi has no user-available Wi-Fi transfer**. A hidden software switch
is not an established explanation for the missing path.

The third-party record alone cannot prove absence of any physical Wi-Fi chip:
original certificate/test report, exact unit label, PCB/revision and possible
separately approved modules remain unverified. Do not upgrade this to “confirmed
no Wi-Fi hardware” or “impossible on every revision”.

Useful reopen conditions: primary certificate/report listing a Wi-Fi module;
vendor's exact-model Wi-Fi instructions; current official App demonstrating an
actual Wi-Fi transfer; or physical module identification. Until one appears,
do not add unverified Wi-Fi commands or repeatedly search the same UI/SDK.
An external coprocessor retrofit would be a hardware-and-firmware project,
not an unlocked feature of the current original firmware.
