# 官方测试板：U2引脚与网络的有界恢复

2026-10-15，本地UTC+8。[机器证据](evidence/actions-official-u2-pin-links-2026-10-15.json)／[复现工具](../tools/inspect_official_tester_pins.py)。纯宿主静态解析，未运行厂商程序或访问设备。

相对[首次材料核查](actions-official-tester-2026-10-13.md)，新增 **U2全部69个声明引脚与69个实际原理图wire端点的一一对应**。原理图U2的part type和used decal均为`ATS3085C_SOCKET`；该实例未旋转／镜像，gate和placed-pin数量均69。它是官方测试板的socket符号声明，不是CoMi实物／芯片datasheet验证。

| U2声明脚号 | 符号名称 | 连接记录的全局网络 |
|---:|---|---|
| 31 | WIO1 | WIO1 |
| 34 | WIO0 | WIO0 |
| 49 | UART0_TX/GPIO28 | GPIO28 |
| 50 | UART0_RX/GPIO29 | GPIO29 |
| 51 | USBDM | USB_DM |
| 52 | USBDP | USB_DP |

全部声明号码恰好`1..69`，其中69号声明GND；不据此独立推断硅片封装或CoMi焊盘。

## 如何建立对应

固定原始SCH SHA256 `078718b5601da3f33e8d5f1a75f147fa1f913d0e716e1c395a49443dc279a68a`。目录元数据固定hash；使用既有KiCad `ac8691a64afa0a78d04f0073e82896bcdec82657` PADS v13 schema和mapper，二者完整SHA也保留。

1. Controller15 placement→9 part type→10 gate→7 used decal；核对名称、gate handle、69个逻辑/实例引脚及顺序。
2. Controller11 pin number／name offset→14 name heap，恢复物理号码和符号名。Controller8 terminal与16 placed-pin给出同序实例位置。
3. Controller21 typed endpoint handle明确指向U2；采用22的首／末vertex坐标匹配符号引脚。没有把未解释的endpoint relationship整数当作pin ordinal。
4. 每个U2引脚恰好匹配一个wire endpoint，其global net索引解析到已固定的全局网络表。69个位置无歧义，所有记录边界、切片原始hex/SHA和坐标转换均保留。

这比字符串邻近搜索或PCB无损往返更强，但只覆盖这个声明实例及其原理图连接。未重建完整器件库、所有sheet拓扑、PCB铜连接、专用ADFU键或独立复位电路。原BOM的V1.2／文件名V1.3修订差异仍未解决。

## 对CoMi的适用边界

可作为后续比对UART／USB逻辑别名、检查官方参考连接的索引。**不能据此给CoMi磁吸触点编号、短接焊盘、认定ATS3085L与C封装相同，或证明ROM退出方式。** CoMi自己的pinmux／板型证据仍以[实机固件分析](board-pinmux-evidence.md)为准；没有新现场接线或刷写结论。

## 离线复现

需保留首次下载的官方包及`artifacts/actions-official-20261013/hardware/schematic-records.json`。工具拒绝source／目录hash不符、未知旋转、越界记录、重复坐标或不完整69-pin join。

```sh
uv run tools/inspect_official_tester_pins.py > /tmp/actions-u2-pin-links.json
uv run python - <<'PY'
import hashlib,json
from pathlib import Path
m=json.loads(Path('docs/evidence/actions-official-u2-pin-links-2026-10-15.json').read_bytes())
actual=json.loads(Path('/tmp/actions-u2-pin-links.json').read_bytes())
assert actual==m['inspection']
for ref in (m['decoder'],m['inspection_artifact']):
 b=Path(ref['file']).read_bytes();assert len(b)==ref['bytes'] and hashlib.sha256(b).hexdigest()==ref['sha256']
print('PASS exact69 declared pins and69 typed wire endpoints; no CoMi/device claim')
PY
```
