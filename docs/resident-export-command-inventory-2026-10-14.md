# 常驻导出入口：实际 shell 目录与 coredump print 边界

2026-10-14；owned CoMi / FW010004；仅离线。**新确认一个使用常驻4096 B缓冲的 NOR 读取链，但 `coredump print` 不能作为通用、无副作用的大块 binary 导出命令。** 它固定读取存储转储、格式化为文本，并可能向固定 backtrace RAM 恢复数据。没有调用该命令、访问设备或修改固件。

[本轮字节证据](evidence/resident-export-command-inventory-2026-10-14.json)保存28段 actual bytes/SHA、SDK文件hash、既有目录及实际ACPT来源hash。镜像927632 B，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`，CPU base `10000000`。地址范围均末地址不含。

## 目录并非新发现

[原静态目录](normal-ram-entry-inventory.md)已经覆盖 root `100ba674..100ba6dc` 的13项、15个静态child表、81个child descriptor；全部dynamic selector为0。本輪重新与镜像核对94个descriptor、15个null terminator、15个selector及array指针。根命令为 `actlog/app/bt/clear/coredump/dbg/devmem/help/history/kernel/resize/shell/system`。不将已有目录重新计算为研究进展，也不把这些静态表等同于全部固件可达接口。

此前[较大binary导出审计](nor-binary-export-boundary-2026-10-14.md)已经排除已审 `snort` 擦写测试、固定512 B `fread`、释放heap、直接 `dumpbuf`、raw alias推断和recovery消费者。本轮不重走那些路径，只追此前目录列出但未展开的 **`coredump print`**。

## 新增完整入口链

| 实际地址 | 字节所证明的行为 |
|---|---|
| root descriptor `100bbfc4` → selector `100bc08c` → array `100bbfd8` | 注册 `coredump`；children为error/erase/find/print/verify。print descriptor `100bc014` 的handler是Thumb `1002e875`，无child selector |
| wrapper `1002e874..1002e880` | 忽略argc/argv；把固定callback `1002e6d8`交给 `1002e75c`；返回0，没有用户地址或长度selector |
| transfer `1002e75c..1002e83c` | 先 `1002e774 BL 1002e598` 验证存储转储；成功才于 `1002e7d0 BL 1002e540`再次读取并格式化；可进入backtrace输出 |
| process `1002e540..1002e594` | 读取16 B header；payload起点固定relative `1000`，长度取header+4；error字段+12须0，累计uint16 checksum与header+10比较 |
| data_read `1002e4a4..1002e536` | context `1800f7b4` 的device和base+2c；通过device+8处API表的+0 read callback读取到静态 `18040632`；不使用已释放heap |
| `1002e4ee..1002e4f2` | 每次driver请求固定 `1000` B，包括header和最后不足4096的消费块；callback/copy只消费min(remaining,4096)，循环按消费长度前进 |
| formatter `1002e120..1002e292` | callback解析转储结构，同时把每32 B转为 `#CD:`+64 hex字符+CRLF；使用常驻printbuf `1804163d`，没有SD二进制输出 |
| output `1002e6d8..1002e6ee` | `printk("%s", data)` → `1009ff86`，随后 `1009c4dc(500)`忙等，再返回0；忽略callback提供的length参数 |

忙等单位已独立核实：`1009c4dc..1009c504` 读取cycle counter、按literal **32,000,000 / 1,000,000** 转换输入并轮询。因此500对应约500 µs，**不是500 ms sleep**。SDK也调用 `k_busy_wait(500)`；这不构成实测吞吐或调度延迟保证。

## 固定分区及副作用

初始化 `1002e638..1002e6b4` 在 `1002e654..65a` 使用file ID `fd`调用实际getter `1002766c`；把entry+12/+16写入context+2c/+30；在 `1002e67a..67c` 绑定真实字符串 `spi_flash`。

[既有两次独立相等、CRC通过的ACPT缓存](partition-readback.md)给出entry13：`coredump`，file ID253，storage0，offset `1f6000`，size `a000`。本轮从原公开blocks重新组装744 B表，SHA256仍为 `a071b0cdafad355eb05a71e96fc2cb6a5348ec8b5e11d0ac4dfe54d83671a144`；entry地址 `01000188`，完整24 B见JSON。**这是历史配置证据，不是新鲜backend context或存储转储header读取。** 未证明当前存在有效转储。

更重要的是print不只是读取/输出：

- formatter在 `1002e226` / `1002e23e` 调用 `10027250`，把存储转储中的特定memory block恢复到RAM。
- `10027250..1002727a`只接受block起点恰好为 `1800e02c`；根据progress把copy限制在 `c88` B内，调用 `100b9652`。这是**固定范围RAM修改**，不是任意地址写原语。
- transfer `1002e7f4` 可继续调用backtrace decoder `10027280`；本轮不展开该decoder，不声称整个print命令无其他副作用或具有可证明执行时限。
- 此print调用链没有调用已审NOR erase/write API，但不能因此抹去RAM副作用，更不能把相邻 `coredump erase` 或capture路径归类为只读。

header校验也不足以作为安全live gate：实际 `1002e55c..566`只在两个magic字节**均不匹配**时拒绝，即接受byte0=`C`或byte1=`D`之一；读取header的返回值未先检查。保存的process/data_read函数没有以context.total_size限制header.size。data_read末尾callback还可替代底层read错误返回。不能用“有checksum”推导畸形header、过长读取或错误传播安全。

## 判决与明确剩余边界

这里新建立了**实际4096 B常驻NOR读缓冲的存在及其固定消费者**，没有建立把任意NOR范围导出到SD/BLE的可调用合同。shell参数不能选择地址/长度；存储转储header控制其范围；输出是文本且有固定RAM恢复。不要执行 `coredump print` 来试探全片导出，也不要把静态buffer地址当作内容/生命周期已验证的活接口。

结论只覆盖这条完整具名入口；不声称全镜像不存在其他出口。未展开其他根handler、动态应用接口或decoder，不提出修改header、注入callback、改MMIO、调用ROM/helper或触发新coredump等绕行。

SDK仅用于对应语义：[固定提交的 flash_dev.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/debug/coredump/coredump_backend_flash_dev.c)；init L138–165、data_read L192–239、process L273–309、formatter/backtrace L748–858、transfer/print L862–929。所有地址、buffer、分支和调用关系来自实际镜像，不以SDK配置替代CoMi字节。

## 离线复验

```bash
uv run python - <<'PY'
import hashlib, json
from pathlib import Path
j = json.loads(Path('docs/evidence/resident-export-command-inventory-2026-10-14.json').read_bytes())
sha = lambda b: hashlib.sha256(b).hexdigest()
b = Path(j['image']['path']).read_bytes(); base = int(j['image']['cpu_base'], 16)
assert len(b) == j['image']['bytes'] and sha(b) == j['image']['sha256']
for r in j['regions']:
    lo, hi = int(r['start'], 16)-base, int(r['end_exclusive'], 16)-base
    raw = b[lo:hi]
    assert lo == r['file_offset'] and len(raw) == r['bytes']
    assert raw.hex() == r['hex'] and sha(raw) == r['sha256']
for key in ('inventory', 'cached_partition', 'sdk'):
    assert sha(Path(j[key]['path']).read_bytes()) == j[key]['sha256']
print('PASS:', len(j['regions']), 'actual-image regions and three pinned sources')
PY
```
