# NOR ring 导出：同一 scratch 文件复用候选

2026-10-14；C261CF0430 / FW010004。**静态链支持一次有界已知内容实验；尚未实测复用。** 本轮只检查固定 actual system 镜像；未执行命令、改工具或覆盖设备文件。目标减少 scratch 文件数量，**不减少 SD 写次数**，不据此推算整片 4 MiB 速度或恢复能力。

[静态收据](../evidence/nor-scratch-reuse-static-2026-10-14.json)：36 段实际 bytes、地址、SHA256；不含私人运行日志。镜像 927632 B，CPU base `10000000`，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。函数名为行为标签，非原厂符号。

## 1. 独立 nonce 不需要新文件名

候选固定命令 `kernel uptime rc0123456789`；实际使用预先生成、两次不同的 `rc[0-9a-f]{10}`。只增加一个无空格、无 shell 元字符的参数，不开放任意命令。

| 实际位置 | 已核事实 |
|---|---|
| `100bb59c` → selector `100bb628` → array `100bb5b0` | `kernel` 静态子命令表；uptime descriptor `100bb5ec` |
| descriptor 20 B | `8a590c1091590c1000000000ad29021000000000`；handler Thumb `100229ad`，mandatory/optional bytes 均 0 |
| `1002315c..317c` | dispatcher 将完整 descriptor 复制到 context+8 |
| `1002323e..329a` | `LDRB [ctx,#18]`；零值直接跳 `10023274`，不执行 argc 上下界检查；`10023298 BLX` selected handler |
| `100229ac..29c4` | 完整 24 B uptime handler：保存 shell 指针，调用时钟，打印 `Uptime: %u ms\n`，返回 0；没有读取入参 argc/argv |
| `100b91f8` → `1009c4a8` | 时钟 thunk / wrapper；临时 BASEPRI 锁、读取累积计数后恢复。没有把额外参数解释成地址或写操作 |
| `1000c2cc..c306` | logsrv 把原文本 buffer 的 `min(len,63)` 位置置 NUL；`1000c2e2` 用 `logsrv: cmd(%d) %s` 记录原文本，再调用 shell |
| `100a0e1a..e58` | shell 先复制原命令再进行 tokenize / dispatch；不反向修改 logsrv 原文本 |

因此该短 nonce 不被 handler 消费，实际 echo 的 `%s` 可完整包含它。命令含 newline 27 B，小于 63 B 上限。**这是接受参数与格式化调用的静态证明；不是新 nonce 已落入当前物理 ring 的运行证明。** 日志调用先于 handler 不保证不同输出路径的保留顺序；已有 fread 实际链为 status → rows → producer echo。必须在新原件中验证 nonce 的实际位置，不能按函数调用顺序重排文本。

## 2. 相同长度从起点覆盖，不 append / truncate

| 实际位置 | 已核事实 |
|---|---|
| `10024a28..4aaa` | 完整 dumpbuf handler：open flags `0x12`，解析固定 address/length，write，close；没有 seek |
| `1002e978` / `1002e9e8` | VFS 保存原 flags 于 file+8，并调用 mount ops+0 |
| ops table `100bc09c` | open `1002f9c1` / read `1002f899` / write `1002f851` / seek `1002f7c1` |
| `1002f9c0..fa16` | 分配并清零 80 B 文件对象，`flags & 0x13`，调用实际 `f_open 1003ff24` |
| `100400d0..00e8` | existing-file 分支检查 create-new bit2、truncate bit3；`0x12` 均不置位 |
| `100401d6..01ee` | `STRD 0,0,[file,#38]` 清零 64-bit cursor；append bit5 分支不取 |
| `1002f850..f894` | write adapter 只有原 flags bit5 才 seek EOF；`0x12` 直接 `f_write 100a714c` |
| `100a7296..72cc` | `size=max(oldsize,newpos)`，更新 cursor；已有完整 4096 B 对象从 0 写 4096 B，长度仍为 4096 B |

**短写不会清除旧尾**；不能改成 512 B 写后把旧 4096 B 文件当新小文件。dumpbuf 忽略 write/close 返回；ACK 与 done 都不证明覆盖完成。必须同时完整下载、核新 nonce、解析 32 行、比独立 oracle。

## 3. Boyi 身份边界

`GET_FILE_DATA` handler `1009edd6..ee0e` 复制 name、解析末尾 32-bit BE offset，再启动 worker；不接受 file-list 授权 token。worker `1000b5b4..b630` 每次创建本地文件对象，**先 open `/SD:/RECORDER/Call-<name>.mp3`，失败才尝试 `Note-`**，flags 3。`1000b688..b6c8` seek EOF / tell / 宣告大小，sleep 100 ms，seek 请求 offset；`1000b676..b67c` 关闭文件。

这支持每次重新打开同一路径，未证明底层缓存必然正确。Boyi offline 数据不携带文件名或事务 ID；完整原 ATT/HCI、单 dispatcher、每次请求/声明/End 以及独立内容关联必须保留。正常 file list 不列出这些 scratch：只能检查可见录音名无冲突，不能证明 scratch 不存在、唯一或更新成功。

候选只选择已由我们创建、原完整下载已保存的一个专用 scratch。可选旧 known-pair 的 boot 文件 `rc52cc41f671`：

- 原目录 `artifacts/dual-known-nor-20261014`，report SHA256 `0f74ac3023f5635740e214ecc9b05bc5b84153dee89c5bb8d2c3201c1c28985d`。
- 原 HCI SHA256 `fec7195c55d2df3ebe583a08357e54881e89f5115c5faa49ab6cab10284050ff`。
- 原 4096 B 下载 SHA256 `a2f7c04b495717e5b851f911f6dbf24471dfbde567c8124da65eb8c9e43b446d`。
- 本轮离线 `dual_nor_probe.replay` 通过两个 known targets。未来实验仍须重放父链，并在**覆盖前**只读下载该同名对象，完整比对原 4096 B hash；不相同则拒绝，不换路径。

原件 host 端不可变保存；设备对象有意被覆盖，不能声称无 SD 修改或已自动恢复。不得选录音、原 RAM oracle 文件或仅 write-attempt、未确认下载的路径。

## 4. 最小新实验合同，尚未实现

一个独立新 profile；固定 boot0 → raw recovery `0x4200`，同 scratch，两次独立 fread / overwrite / download。只做 known-content 判别，不称 unknown NOR 双读或新增 coverage。保留既有 code / identity / idle / HCI / status-event / before-state 门槛；新 uptime 与 dispatcher 静态片段需纳入新入口身份预检，不能直接把旧 5-ACK profile 当作新合同。

每次 Actions 严格顺序：

1. PREPARE、START。
2. `kernel uptime rc<本次10hex>`：含 newline 27 B。
3. 固定 `dbg fread spi_flash 0` 或 `dbg fread spi_flash 0x4200`：22 / 27 B。
4. 相同 `dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rc52cc41f671.mp3`：含 newline **63 B**。
5. STOP；合计 **6 ACK + F1 + pending 空**。不用 uptime 数值证明新鲜度，不追加命令填充。

每次都要独立保存实际 ATT span、完整 4096 B、512 B candidate、原环形索引证明。正常化 / slow 结算 / identity barrier 复用已验 per-download window；不得假定额外 uptime 活动不会改变参数事务，实际不符合已审状态机即失败停止。首项全通过才进行次项；无 retry、无新文件替代。

新解析门槛，**不能修改历史 strict parser 含义**：

- 两 nonce 在覆盖前原下载均不存在，彼此不同；第二 nonce 在第一份实际下载也不存在。先冻结计划、父件 SHA 和唯一专用路径。
- 一圈 4096 B 内唯一完整本次 uptime echo，长度字段必须等于实际含 newline 长度；其后仅一个当前 status / 32 连续 canonical rows / 最近精确 producer / 当前 dump 组成有效链。任何 failure/error、另一 status/producer、截断或跨超过一圈均拒绝。
- 本次 nonce 必须完整位于当前 status 之前；若异步日志导致不满足，**停止该候选**，不移动 nonce、不重排、不删行补链。uptime 输出完整性由实际 Actions 保留另验，不能用“没报错”替代。
- 相同 dump 文本可历史残留；旧 `_unique_dump` 全圈唯一条件及 `previous_dump != dump` 已不适用。新合同只能在唯一 fresh nonce 后匹配唯一当前 dump；旧相同 echo 必须位于该 nonce 之前。当前 scope 内有两个 dump 仍拒绝，禁止按 oracle 相等挑 candidate。
- status → 32 行 → producer → dump 的原格式、地址、failure 扫描保持。至多一个已审 exact composer fps2 notice 仍只能在原指定 gap；不能泛化成跳过任意日志。
- boot0 原始 512 B oracle SHA `72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`；4200 oracle SHA `51327e9d7a7d8d4c3538c83688753b5f99735b85e981756effb63efd1dc33713`。来自独立 boot / recovery 原件，不从本次输出生成。
- 精确 4096 B 声明、接收、End、真实下载 window 与 nonce / raw oracle **全部**成功才可证该次覆盖导出。任一失败保留 partial / state / HCI，不宣称文件更新，也不继续覆盖。

必要离线反例：旧完整 rows + 新 uptime nonce + 本次 fread failure；nonce 未保留；重复 nonce；第二 producer/status；旧 same-dump echo；两候选；wrap / 截断；正确 nonce + 旧错误 target 内容；短写保留旧尾；第二项失败仍保留第一项而整体失败。原 5-ACK 成功/失败 archive 重放结果不得改变。

## 5. 判决与复验

**可进入实现评审的候选，尚非已验证复用能力。** 三条静态边界已闭合：额外 uptime 参数不执行未知操作；完整 nonce 可传入 echo；同长文件写从起点开始且后续下载重新 open。真正剩余门槛是新 nonce 在保留 ring 中的顺序/完整性和实际覆盖后内容，必须由上述两 known targets 实验决断。

即使成功，也只把 scratch 数量从随读取次数增长改为一个受控对象；每次仍写 4096 B 与文件系统元数据，仍文本读取 512 B，不解决吞吐、原子性、已释放 heap、全 NOR 覆盖、擦写或可恢复性。

离线复验（不访问设备）：

```sh
uv run python - <<'PY'
import hashlib, json
from pathlib import Path
j = json.loads(Path('docs/evidence/nor-scratch-reuse-static-2026-10-14.json').read_text())
b = Path(j['image']['path']).read_bytes()
assert len(b) == j['image']['bytes']
assert hashlib.sha256(b).hexdigest() == j['image']['sha256']
base = int(j['image']['cpu_base'], 16)
for r in j['regions']:
    raw = b[int(r['start'], 16)-base:int(r['end_exclusive'], 16)-base]
    assert len(raw) == r['bytes'] and raw.hex() == r['hex']
    assert hashlib.sha256(raw).hexdigest() == r['sha256']
print('verified', len(j['regions']), 'actual-image regions')
PY
```

相关边界：[原 SD bridge](../sd-file-bridge.md)、[fread 生命周期](../raw-read-handler-followup.md)、[shell 入口](../shell-text-readback.md)、[原严格 freshness parser](../../src/rcominote/experiments/nor_freshness.py)。
