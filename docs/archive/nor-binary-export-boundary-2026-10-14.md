# 较大 binary NOR 导出：已审入口边界

2026-10-14；owned CoMi / FW010004。**已审入口中未建立安全的较大 raw NOR→SD/BLE 二进制出口。`snort` 虽接受 size，却实际执行擦除和写入，禁止用于只读实验。** 这是具名入口、固定代码及已有材料的有界结论，不是“全镜像不存在其他途径”。本轮没有设备操作、helper执行、MMIO访问或源码修改。

[字节证据](../evidence/nor-binary-export-boundary-2026-10-14.json)保存20段 actual image bytes/SHA，包括完整三个函数、独立 literal pools、descriptor、字符串及RAM wrapper初始载荷。系统镜像927632 B，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。CPU base `10000000`；代码用Capstone Thumb/MCLASS完整解码，literal不计为指令。

## 新增判决：snort 不能替代 fread

实际静态表 `100bb94c` 为完整20 B descriptor：syntax=`100c6b3f`的 `snort\0`，help=`100c6b45`的 `nor test : snort address size\0`，handler Thumb指针=`100257d5`。这是已知 `dbg` 表中的相邻命令，不是按SDK名字猜入口。

| 实际范围，末地址不含 | 完整行为 |
|---|---|
| `100257d4..10025848`，116 B | 绑定 `spi_flash`；argc==3时base0解析offset/size，否则使用offset `20000`、size `e0000`；打印参数，调用read-speed，再调用erase/write/readback测试；最后返回0 |
| `10025564..10025618`，180 B | 分配512 B；按512递增offset调用device API+0；只输出状态/速度，不输出读到的buffer；读失败退出循环，释放buffer后仍返回0 |
| `10025628..100257ac`，388 B | 分配512 B并填入128个word的index模式0..127；先逐64KiB擦除，再逐512 B写入模式，最后读取比较；释放buffer，返回0 |

三个 literal pools 分别为 `10025848..854`、`10025618..628`、`100257ac..7d4`，在JSON中独立保存，不误解码成控制流。

决定性调用顺序：

1. `1002582a BL 10025564`，随后 `10025836 BL 10025628`；两者间只有重新装载相同参数，**不检查读测速返回值**。前一步malloc失败也不构成后续写测试的停止门。
2. `10025686..68a` 按requested size控制擦除循环。`10025756..766` 从device+8取API，再取API+8；BLX前传offset+progress及长度 `10000`。这是64KiB擦除请求，不按最后剩余size缩短。
3. `10025766..778` 对负返回值打印真实字符串 `flash erase fail`，随后仍加 `10000` 并继续；擦除阶段结束后进入写阶段。
4. `100256c0..6d2` 从API+4取write callback，传pattern buffer和固定512 B。非负结果加512继续；负结果退出write循环，但仍进入后续timing/readback流程。
5. `10025722..732` 从API+0读取512 B；`10025780..7a8` 将每word与0..127比较。该数据是测试模式，不是原NOR字节备份；不匹配只输出诊断并推进。
6. `1002574e` free，`10025752` 返回0；最外层也返回0。因此ACK或handler返回0不能证明没有修改或测试成功。

API角色有两层依据：实际指令选择+0/+4/+8与真实read/write/erase诊断字符串一致；固定SDK的 [`flash_driver_api`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/flash.h#L141)采用对应read/write/erase排列。SDK是语义对照，不声称与CoMi完全同源编译。

[既有实读API前缀](../boot-storage-device-readback.md) `18001aa4` 为 `1800006d / 180000b1 / 180000c5 / 180000d1`；启动载荷 `100defa4` 与其相符。本轮同时保存actual RAM wrapper的镜像载荷：

- `180000b0..180000c0` 将device.data与写参数转交表 `100bc294+18`，其Thumb目标 `18000ead`。
- `180000c4..cc` 将device.data与擦除参数转交表 `100bc294+1c`，其Thumb目标 `18001075`。
- 这是初始化载荷/已有实读表的对应关系，不是本轮新鲜RAM采样或实际函数调用记录。无需进一步执行底层callee，现有明确擦写路径已足够否决 `snort`。

**冻结规则：不实测 `snort`，不靠size=0、特殊offset、malloc失败或返回码试探。** 它没有“仅read”selector；对默认参数尤其不能调用。

## 其余已审路径为什么还不能放大

| 入口/证据 | 已知能力与剩余断点 |
|---|---|
| [`fread 10025348..100253fa`](../raw-read-handler-followup.md) | `spi_flash` 固定512；成功数据经 `100252e4` 格式化，返回前free。不能通过额外length参数获得更大buffer，更不能读取释放后heap来替代生命周期合同 |
| [`dumpbuf 10024a28..10024aaa`](../sd-file-bridge.md) | 将给定memory pointer/length直接传fs_write；没有NOR read参数或由NOR填入受控buffer的内部桥接；忽略write/close结果 |
| [`1800006c → 18000d10`](../nor-driver-readback.md) | 底层read长度参数化，wrapper按最大 `8000` 字节拆块；这不等于存在可调用的较大导出命令。此次未发现已审caller能把有效buffer直接交给binary输出 |
| [`40010300/304` slot0](map0-entry-live-2026-10-14.md) | 两份历史实测为 `1000000f / 00024000`；不证明整片raw alias、映射窗口尺寸或可逆变换。小XIP CPU-copy成功仍是mapped表示，不能替代未知物理字节 |
| [Boyi `1009edd6 → 1000b5b4`](nor-scratch-reuse-plan.md) | 打开既有Call-/Note- SD对象，offset→EOF；没有已证明raw NOR地址/长度模式 |
| 完整实际/官方recovery比较 | actual `1100442c → 11004248` 是TEMP分区→OTA消费者；constructor/state/protection有副作用，未建立安全外部备份命令。见 held `artifacts/actions-official-20261013/astra-backup-route/route-summary.json`，不重启进入此路径 |

没有将未展开的其他命令、动态callback或ROM能力一概判为不存在。当前约束下不提出释放heap、改MMIO映射、模式切换、ROM/helper或固件注入绕行。

## 当前可试收益与规模限制

[同scratch复用候选](nor-scratch-reuse-plan.md)解决文件数量：独立nonce关联两次known producer，同一4096 B对象完整覆盖/下载/验收。它仍每512 B NOR payload写出4096 B日志以及文件系统元数据，不减少SD写次数。

4MiB按512 B共8192个block；一遍8192次producer，独立双读16384次，再扣除确有独立来源的已覆盖部分。这里仅给数量级算术，不从少量成功会话推算可靠吞吐或37h ETA。完整fw1_boot取得不等于整片raw备份、NOR可写或可恢复。

## 只读复验

JSON已包含全部关键字节，根目录可独立校验，不依赖设备或Ghidra工程：

```bash
uv run python - <<'PY'
import hashlib, json
from pathlib import Path
j = json.loads(Path('docs/evidence/nor-binary-export-boundary-2026-10-14.json').read_bytes())
b = Path(j['image']['path']).read_bytes(); sha = lambda x: hashlib.sha256(x).hexdigest()
assert len(b) == j['image']['bytes'] and sha(b) == j['image']['sha256']
base = int(j['image']['cpu_base'], 16)
for r in j['regions']:
    lo, hi = int(r['start'], 16)-base, int(r['end_exclusive'], 16)-base
    raw = b[lo:hi]
    assert lo == r['file_offset'] and len(raw) == r['bytes']
    assert raw.hex() == r['hex'] and sha(raw) == r['sha256']
for source in j['sdk']['files']:
    assert sha(Path(source['path']).read_bytes()) == source['sha256']
print('verified', len(j['regions']), 'actual-image regions and pinned SDK files')
PY
```
