# Linux LE features 失败为何显示 errno38

2026-10-14；owned CoMi / FW010004；Ubuntu `6.14.0-36-generic`。**本次 `OSError: [Errno 38] LE ATT connect failed` 是 HCI status `0x3e` 经 Linux 默认错误映射得到 ENOSYS，不能据此称 ATT 不受支持。** 无设备操作、模块加载、控制器重启或旧失败改判。

[机器可复验收据](evidence/linux-le-features-error-2026-10-14.json)固定本机模块、完整上游源文件和关键行片段 SHA、实际机器码，以及原 HCI 的四个相关记录。原始源码副本及 objdump 位于 ignored `artifacts/linux-le-features-error-20261014/`。

## 原失败记录

`artifacts/startup-boot-tail-20261014/2e00/session.btsnoop`：950 B / 23 records，SHA256 `e029bbe3a153db7c183e9555e5fbc05afbbd122d21ef83c527a941b9f32ab060`。独立遍历确认每条 included/original length 相等、drops0、文件完整；零 ACL、零 ATT。

| Record | 实际含义 |
|---|---|
| 18 | LE Enhanced Connection Complete，status0，handle `0x0800` |
| 21 | LE Read Remote Features，opcode `0x2016`，handle `0x0800`；hex `1620020008` |
| 22 | 上述命令 Command Status0；hex `0f0400011620`，仅表示命令被接受 |
| 23 | LE Meta event `0x3e` / subevent `0x04`；**payload status 也是 `0x3e`**；hex `3e0c043e00080000000000000000` |

18→23 为 **321.968 ms**；21→23 为 **307.869 ms**。HCI 外层 event code 与内层失败 status 数值相同，含义不同。连接事件成功不等于后续 features exchange 或 GATT 已可用。该文件没有断连事件；不能补造正常断连或声称观察到失败后的 identity。

原 pair：`ok=false`、ATT0、before/after均不存在；两 operation 无 Actions 起点、无 producer、`sd_write_attempted=false`。最新经实际身份查询确认的 state 仍是上一成功 `2c00.after`，free59590。

## 本机机器码直接证明映射

本机 `/lib/modules/6.14.0-36-generic/kernel/net/bluetooth/bluetooth.ko.zst`：

- 压缩 SHA256 `ed1e14b18580c85e9eebefcb6f5d1c5f5a1a007ac16b00c0aac211a8b7a43b06`。
- 解压 ELF SHA256 `4d0f5586d7fb2ad52ff4782e05e0558efed43035cc737e571f3807d6af33fe2a`。
- `bt_to_errno` 位于 relocatable ELF `.text+[0x58900,0x58926)`；**不是运行时 kernel VA**。
- `+0x06 mov eax,0x26` 先设返回值38；`+0x0e cmp di,0x3c`；`+0x12 ja +0x1e`。输入 `0x3e` 大于 `0x3c`，直接跳过查表，保留 EAX=38 返回。该路径不依赖 relocation 查表地址。

本轮只解压、静态反汇编已安装模块文件，没有加载或执行该模块；未读取运行中模块内存。实际安装文件机器码证明映射，上游源码说明调用关系；不能声称捕获了完整 Ubuntu 内核运行栈。

## 上游 v6.14 调用链

1. [`hci_event.c` 6453–6493](https://github.com/torvalds/linux/blob/v6.14/net/bluetooth/hci_event.c#L6453)：`hci_le_remote_feat_complete_evt` 对 BT_CONFIG 连接把 `ev->status` 传给 `hci_connect_cfm`。特殊放行只针对特定 inbound unsupported-remote-feature 情况，本次 `0x3e` 不属于它。
2. 本机 headers `include/net/bluetooth/hci_core.h` 2031–2044：`hci_connect_cfm` 分派已注册 callback。[`l2cap_core.c` 7567–7572](https://github.com/torvalds/linux/blob/v6.14/net/bluetooth/l2cap_core.c#L7567) 注册 L2CAP callback。
3. [`l2cap_core.c` 7185–7200](https://github.com/torvalds/linux/blob/v6.14/net/bluetooth/l2cap_core.c#L7185)：非零 status → `l2cap_conn_del(hcon, bt_to_errno(status))`。
4. [`lib.c` 66–156](https://github.com/torvalds/linux/blob/v6.14/net/bluetooth/lib.c#L66)：没有 `0x3e` case，default返回 ENOSYS；`0x11/0x27/0x29/0x20` 才映射 EOPNOTSUPP。这与本机机器码独立吻合。
5. [`l2cap_core.c` 1751–1791](https://github.com/torvalds/linux/blob/v6.14/net/bluetooth/l2cap_core.c#L1751) 将 err 传入 `l2cap_chan_del`；646–655再调用 teardown；[`l2cap_sock.c` 1561–1608](https://github.com/torvalds/linux/blob/v6.14/net/bluetooth/l2cap_sock.c#L1561) 设置 `sk->sk_err=err` 并唤醒 socket。
6. 项目 [`linux_att.py`](../src/rcominote/linux_att.py) 101–123 在非阻塞 connect 可写后读取 `SO_ERROR`，非零则抛出上述 OSError。该字符串只标记 host 连接阶段，不是 peripheral ATT Error Response。

## 离线复验

仓库根目录运行以下片段，仅创建临时解压文件，不加载模块或访问设备。源文件缺失时按 JSON 内官方 URL 获取并核 SHA；不要拿其他内核版本替代。

```bash
uv run python - <<'PY'
import hashlib, json, struct, subprocess, tempfile
from pathlib import Path
j = json.loads(Path('docs/evidence/linux-le-features-error-2026-10-14.json').read_bytes())
sha = lambda b: hashlib.sha256(b).hexdigest()
h = j['host']; compressed = Path(h['module_path']).read_bytes()
assert sha(compressed) == h['compressed_sha256']
elf = subprocess.check_output(['zstd', '-dc', h['module_path']])
assert sha(elf) == h['elf_sha256']
with tempfile.TemporaryDirectory() as d:
    p, t = Path(d)/'module.ko', Path(d)/'text.bin'; p.write_bytes(elf)
    subprocess.run(['objcopy', '--dump-section', f'.text={t}', str(p)], check=True)
    lo, hi = map(lambda x: int(x, 16), h['range_hex'])
    region = t.read_bytes()[lo:hi]
    assert region.hex() == h['bytes_hex'] and sha(region) == h['region_sha256']
for source in j['sources']:
    b = Path(source['path']).read_bytes(); assert sha(b) == source['sha256']
    for region in source['regions']:
        lo, hi = region['lines_inclusive']
        assert sha(b''.join(b.splitlines(keepends=True)[lo-1:hi])) == region['sha256']
c = j['original_hci']; b = Path(c['path']).read_bytes()
assert sha(b) == c['sha256'] and len(b) == c['bytes']
pos, records = 16, []
while pos < len(b):
    original, n, flags, drops, stamp = struct.unpack('>IIIIQ', b[pos:pos+24])
    data = b[pos+24:pos+24+n]
    assert original == n == len(data) and drops == 0 and flags & 65535 not in (4, 5)
    records.append((stamp, data.hex())); pos += 24+n
assert pos == len(b) and len(records) == 23
for row in c['selected_records']:
    assert records[row['record']-1] == (row['timestamp_btsnoop_us'], row['hex'])
print('module, source regions and original23 HCI records verified')
PY
```

## 下一连接边界

无线/控制器/peer 为什么返回 `0x3e` 尚未知；错误映射闭环不等于修复根因。原 job/2e失败保留。可从原2560来源及两份实际成功2a/2c各512重放建立3584前缀；失败2e不增加覆盖。

后续新单2e pair应在**同一新连接**内先严格通过实际GATT、精确最新identity/state、startup结算，再发producer；失败即停，不自动重连。两独立producer/nonce完整512一致，且3584旧来源再次重验后，才装配4096。此设计无需额外健康连接，也不声称完整4MiB备份或恢复能力已经具备。
