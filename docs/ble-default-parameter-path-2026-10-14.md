# BLE startup DEFAULT 与日志控制 pulse：实际固件边界

2026-10-14；C261CF0430 / FW010004。**新 `24..40 / latency0 / timeout500` 请求来自实际连接层默认参数候选，不是应用 FAST/BUSY/IDLE 表。** 本轮只离线核查已保存镜像与 HCI；未运行 pulse、修改旧失败或放宽协议解析。

[静态收据](evidence/ble-default-parameter-path-2026-10-14.json)保存原 15 段参数路径，以及 literal / Actions 控制路径，共 30 段 bytes/SHA。镜像 927632 B，CPU base `10000000`，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。名称是行为解释；地址、指令和常量来自 actual image。

## 默认参数与应用参数不同

| 来源 | min / max / latency / timeout |
|---|---|
| connection default `100ba772`，8 B | **24 / 40 / 0 / 500** |
| Android FAST `100c0550` | 6 / 12 / 0 / 500 |
| Android BUSY `100c0558` | 36 / 72 / 0 / 600 |
| Android IDLE `100c0560` | 32 / 48 / 4 / 600 |
| iOS FAST `100c0568` | 12 / 12 / 0 / 500 |
| iOS BUSY / IDLE `100c0570 / 578` | 同 Android BUSY / IDLE |

默认 8 B 精确 hex：`180028000000f401`。`100747e0` literal=`100ba772`。应用 selector `1006bc5c` 取 global phone byte+`0e`，另一个 `1006bdbc` 接受显式 phone/speed，二者按 `(phone*3+speed)*8` 索引 `100c0550`；都没有 24..40 表项。

实际更新路径：

1. `100b23a2` wrapper → `100b37d2`。若当前 interval 在请求 min/max 内，且 latency/timeout 相同，`100b37fa..3808` 清 connection flags **bit9**，返回 −120。这是匹配参数 no-op，不产生新的更新请求。
2. 不匹配且 peripheral deferred 尚未完成：`100b3826..3856` 保存请求于 connection+`a8/aa/b0/b2`，置 bit9；已过 deferred 阶段则直接发送。
3. 完整 deferred worker `10074764..47e0`：`100747a4` 调 test-and-clear bit9 helper `100b344e`；有 pending 则复制保存参数，无 pending 则 `100747d4..47de` 从 `100ba772` 复制默认 tuple。
4. `100747b6` 调 `10074708`；按 feature/role 分支可尾调用 `100b4144` 的 L2CAP 参数请求路径。worker 随后置 flags bit8，表示 deferred 阶段已过。相似 SDK `conn.c` 381–433、2189–2228 也有这两个分支；**实际 tuple 不从 SDK 宏推测**。

本次初始连接 `12/0/500` 已满足 Android 与 iOS FAST，所以应用 FAST no-op 后允许 delayed DEFAULT 出现；前次初始 `48/4/600` 不满足，会保存 FAST pending。这是有实际指令支持的解释，**不是已观察到 CPU 执行该路径**。更不能仅凭前 health 最终 interval12 与新连接 interval12 相同就证明主机缓存的具体实现。

## 失败原件中的实际事务

`artifacts/status-remaining-20261014/2a00` 原失败保持不变；report SHA `03165ecada9f4d8bf178eec4b8e94352b0f5f34d0b4e8fdc3d34b3711cc08be6`，HCI SHA `bc8a88ab18853c551bbe34c9330cd4975370493e449ee6bfcb007721729401fe`。

独立 `param_window.inspect` 完整复验 119 records / 4995 B：

- record18：新连接成功，handle2048，实际 `12/0/500`。
- record104：CID5 remote request，id5，精确 `24..40/0/500`；在 connect 后 **5.012130 s**。
- record106：success accept；107：同 handle HCI request；108：status0；110：Update Complete status0，实际 **36/0/500**。
- final pending 空；没有本次 Actions/NOR producer/SD write。初始和最终 identity 相同，不把失败改为成功。

5.012130 s 是这份 HCI 的时间差，不是从代码证明的所有连接固定等待上界。HCI 无本次 disconnect；不能据此补造已结束事件。

## DEFAULT 后活动提速的实际条件

参数回调 `1006b2b4..b2f4` 用 `interval*(latency+1)` 与 phone FAST.max / BUSY.max 比较。`36/0` 分类为 speed1。通知发送函数 `1006bfc8` 中 `1006c014..c020`：speed 非零，且 global BR 活动 bits1/2 均未置时，调用 `1006b3d4`。

`1006b3d4..b402` 只安排已有 delayed work：idle 分支使用常量50，running 分支使用4000，其他状态不重复排程。worker `1006bcc0..bda2` 还检查 TX/RX counter 增量；正常无回绕增量必须 **>3** 才判忙，并考虑 BR flags 与已记录 speed，再通过应用表 selector 请求 FAST。不能把“经过 send 函数”当作“必然请求 FAST”。NOTE/idle 身份字段也不能证明内部 BR flags。

## 只用 PREPARE / START / STOP 的 pulse

固定 packet 为 `1d108105000002000100` / `1d108105000002002000` / `1d108105000002002100`。全部是 type0、length2 控制 code，无 type1 shell 文本。

| 实际位置 | 效果 |
|---|---|
| `1000c25e..c2c8` | 验证 code 长度2；PREPARE1 置 ctx+4 bit1；START20 设置 new_type0；STOP21 设置 new_typeff |
| `1000c19c..c1bc` | 当前命令 TLV 消费完后经 `1000bb5c` 发 ACK |
| `1000be74..bf20` | 模式改变清 16 B slot lengths、`rd=wr`、drop=0；DEFAULT 注册 user backend，timer 参数10/10；STOP 注销 backend、发送 F1，timer50/50 |
| `10056510..56550` | register/unregister 完整叶函数只设置/清 RAM callback/context `18018c88/18018c8c`；mode 固定 `0x10` |
| `1000c072..c09c` | disconnect 路径清 ctx+4 bits0/1；STOP 本身不清 PREPARE bit |
| `1000bb5c` → `100517fc` → 已审 stream ops | ACK/F1 经同一实际 BLE writer；`100b19fa` 调 `1006bfc8`，故会经过活动检查 |

已检查控制分支没有 shell handler、文件写、NOR读写、录音或重启调用；也不是 `dbg dbgsw` CPU/DMA 切换。**它会改变日志 RAM、callback 和 timer，并产生协议流量与日志**，不能描述成完全无副作用。未穷尽固件其他后台行为，不能借此保证物理 NOR 永远没有后台日志写入。

Pulse 验收应为 **3 ACK、F1、pending 空**，不是“恰好三个通知”。期间有界 F0 背景日志仍须完整解码；溢出、迟到包、STOP 不完整立即失败。新 `run_commands` 若支持零 body，旧 NOR `run` 仍固定两 body/5 ACK，不能改历史成功 proof。

## 最小 known-RAM 对照建议

该设计有新的可判决变量：先建立实际 DEFAULT，再用控制 pulse 观察 FAST 恢复；不直接重跑失败 NOR job。

1. Seed 独立只读连接：GATT/identity → **真实 FAST 完整事务** → identity → close；被动捕获同 epoch disconnect，最多8 s。没有 FAST / disconnect 即失败；不循环 seed，不凭 close 调用推断断链。
2. Data 新连接：必须真实 DEFAULT `24..40/0/500` 完整结算且无 pending，实际 interval 落入范围。若只有 FAST，保存 failed control、结束；不称已测试 DEFAULT。Seed 不能保证新连接一定选12，也不能保证 DEFAULT 一定出现。
3. 第一轮固定三包 pulse → 有界等待真实 FAST 完整事务 → 一次 host `6/6/0/500 CE1/1` 归一 → 下载原已拥有 RAM4096 → EOF SLOW完整结算 → identity。第二轮重复；无 shell producer、SD写或NOR读。
4. 每份下载独立4096 B、精确原 RAM oracle、完整 ATT/HCI 绑定；GET_FILE_DATA TX→End 期间实际参数始终6/0/500；EOF slow 的请求与应用时点仍按既有 window 合同检查。两次独立保存，不拼 partial。
5. FAST 可能由前置 identity / 通知活动触发，不能仅凭先后顺序断言 pulse 是唯一原因。若研究合同要求“pulse 后 FAST”，就明确要求 request record 不早于 pulse 首 TX；先到的 FAST 不能重命名为 pulse 结果，也不能漏出事务账本。不重复 pulse 凑计数。
6. 所有 startup / FAST / normalize / SLOW 均完整消费，pending 空；每轮 barrier 与最终 readonly state 必须通过。任何失败停止并保留原件；绝不因 tuple 看似合理而忽略额外事务。

Seed 与 data 各自 deadline/capture 生命周期独立有界；8 s 被动收尾必须计入其全局预算，不能让55 s monitor硬超时替代正常 SIGINT收尾。新控制成功最多证明这种已知 RAM 路径与参数状态转换，尚不是 unknown NOR job 或规模化成功。

## 复验

```sh
uv run python - <<'PY'
import hashlib, json
from pathlib import Path
j = json.loads(Path('docs/evidence/ble-default-parameter-path-2026-10-14.json').read_text())
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

源码对照仅帮助命名：[固定 SDK conn.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/bluetooth/bt_stack/src/bt_stack/conn.c)、[log_service.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c)。实际 BLE stream 绑定见[已有发送链证据](evidence/android-tx-path-2026-10-13.json)，日志 RAM 非 printk snapshot 锁，参见[模式边界](log-ring-freeze-boundary-2026-10-14.md)。
