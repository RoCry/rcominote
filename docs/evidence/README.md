# 证据索引

日期：2026-10-12。历史说明、源码事实和本轮实测分开；历史文本中的绝对路径只用于追溯，不是运行依赖。

## 首轮实测（419b628）

- [gatt-2026-10-12.json](gatt-2026-10-12.json)：`uv run tools/gatt.py --out artifacts/gatt-2026-10-12.json`，UTC 02:18:21；广告序列号选中 `C261CF0430`，连接后枚举，无应用特征读写/通知订阅。4 个服务，MTU 247，日志服务存在，普通模式 OTA 服务未出现。macOS 缓存/设备当前模式限制仍适用，不是所有模式的证明。
- `uv run tools/comi.py info`：GET_SERIAL / GET_BIND_INFO / GET_DEVICE_INFO 通过 Boyi 写请求、收通知；序列号吻合，unbound，idle，FW `010004`，total/free `59634/59632`，charging，battery 100，USB mode true。状态 payload：

  ```text
  0000e8f20000e8f00264000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000
  ```

- `usb-devices --json`：可见 Hiveton 与 Espressif 串口，未进行 probe/refresh/reset；串口清单不等于全 USB 清单，未确认 CoMi USB 接线。本轮不靠该结果推断 CoMi 芯片。
- 格式/lint/7 个离线捕获帧测试及 CLI help 见 `just check`。未构建 SDK、未刷机、未调用日志 shell；历史 HIL 不算作本轮重测。
- `tools/apk_evidence.py` 对两个固定 APK 样本均成功：1.1.2 为 1,781 个成员/11 个片段，1.2.4 为 2,165 个成员/0 个匹配片段；核对片段摘要，并验证未知哈希、已有输出目录会拒绝。完整提取文件在忽略的 `artifacts/`，复现命令见 [APK 核查](../app-upgrade.md)。

## 迁移来源

rlcdv commit [`027b547a26c624ff7b61b8e96b9327f7643671d9`](https://github.com/rocrp/rlcdv/commit/027b547a26c624ff7b61b8e96b9327f7643671d9)，`research/comi/{comi.py,protocol.py,test_comi.py}`。交接写 PR 未合并，但本轮主仓已有该提交/目录，不再依赖已消失的 worktree。

迁入 `tools/` 后，CLI 加入按广播序列号精确选设备，删去旧项目专属注释/格式整理；协议和既有 oracle 测试内容保持原样：

| 文件 | SHA-256 |
|---|---|
| `tools/protocol.py` | `ebab4ac25d787061fdbb6e46f3c67f93bdd85414fcb9991655a51c8efb99794b` |
| `tools/test_comi.py` | `d5e110b0604b9ce58b3f3fb9cec30551c4790cc3e22a12580db8dbf3763dae0c` |

## 历史快照与修正

- [handoff-2026-10-12.md](handoff-2026-10-12.md)：用户指定交接文档完整快照。
- [prior-device-research.md](prior-device-research.md)：既有设备研究笔记快照；原始抓包测试、MP3 与包装信息来源。含历史路径/旧链接，当前导航以仓库 README 为准。
- 两份历史文本的“USB 仅充电 / 已有可执行 shell / OTA 默认无签名”等表述不作为当前结论。修正见 [路线](../firmware-roadmap.md)、[SDK 核查](../actions-sdk.md)、[APK 核查](../app-upgrade.md)。

APK/SDK 由各专题文档记录样本哈希、固定版本及复现入口。原始录音、完整 APK、厂商/第三方 SDK 不纳入 Git。

## 第二轮：USB 对照与日志握手

- [USB 对照记录](../usb-log-probe.md)：用户确认数据线；connected→unplugged 无节点变化；reconnected 仅另一台 Hiveton/rcwodle 身份变化。完整原始 USB 树放忽略目录，报告保留摘要及哈希。
- [log-prepare-2026-10-12.json](log-prepare-2026-10-12.json)：一次固定 PREPARE、一次精确 ACK；本轮确实写了日志控制特征，但未发送 shell、dump、复位或存储命令。它取代“仅有 UUID”作为更强的平台证据，不证明 shell。
- 新增 USB oracle fixture来自实际 IOKit 描述符，格式/lint、共 8 个测试通过；新版工具实机运行。SDK 仍未构建，未刷写/备份原厂固件。
