# 证据索引

日期：2026-10-12。当前工具已迁入uv包，旧脚本路径对应各轮历史提交；现用命令见[CLI](../cli.md)。历史说明、源码事实和本轮实测分开；历史文本中的绝对路径只用于追溯，不是运行依赖。

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

## 第三轮：Ubuntu 参考应用编译

- [ubuntu-build-2026-10-12.json](ubuntu-build-2026-10-12.json)：804 步干净构建、工具/依赖版本、ELF/BIN/HEX 与配置哈希、SDK 零 tracked 改动。
- [实测报告](../ubuntu-build.md)：第一次发现 freetype 写回 SDK，外部 CMake hook 修正后第二次干净构建成功；两次 BIN/HEX 哈希相同。
- 本轮没有 BLE/USB 设备操作，没有打包或刷机；GDB/完整 vendor maker 仍未验证。完整构建日志与镜像留在忽略的 artifacts 目录。

## 第四轮：实机 shell 与有界 NOR 读取尝试

- [诊断报告](../device-diagnostics.md)：默认日志、版本、帮助、NOR 头读取五次独立会话。原始通知/写入/解析文本均存入同目录 `log-{default,device-info,commands,flash-header,flash-header-flushed}-2026-10-12.json`。
- 版本正文 Zephyr 2.7.0；device 模块未找到；帮助列出 fread/snandr/reboot adfu。NOR 读取仅收到 handler 状态行，未获得512字节数据，不能当固件备份。
- 每次已收到 STOP ACK/F1；最后 Boyi 查询成功，FW/容量/idle 未变。未重启、擦写、运行恢复入口或 flash helper。
- `just check`：格式/lint/脚本语法、10 个离线测试通过，包括真实分片日志与中途断流回放。

## 第五轮：NVRAM 单键读回与 REA 归档核查

- [platform-info](log-platform-info-2026-10-12.json)：app/system 帮助、固定两个 NVRAM getter；BT_LE_NAME 返回14字节，FW_VERION失败。没有写配置；会话 STOP/F1 完整，后续 Boyi info 正常。
- [REA 1.2.4 归档摘要](rea-apk124-inventory-2026-10-12.json)：保留实际 Evidence ID/限制；完整 bundle 留 artifacts。Android provider 缺少调用者提供的 JADX MCP JAR，没有执行反编译。
- [APK 不透明文件](apk124-candidates-2026-10-12.json)：普通 ZIP 字节核查，独立于 REA；包含准确 SHA/熵/有限字面搜索范围。未发现可用原厂固件，未证明这些文件的用途。
- `just check` 格式/lint/语法及11个离线测试通过；新 oracle 对照真实 NVRAM 字节响应。

## 第六轮：线程、代码读回与远程页面入口

- [kernel帮助](log-kernel-help-2026-10-12.json)、[线程](log-threads-2026-10-12.json)、[紧凑栈表](log-stacks-2026-10-12.json)：后者25条线程+IRQ；详细线程输出在设备端截断，ACK/F1完整不代表正文完整。
- [首次16字节](log-code-sample-2026-10-12.json)、[独立重读](log-code-sample-repeat-2026-10-12.json)、[Capstone离线报告](code-sample-analysis-2026-10-12.json)：两次相同，全部解码；报告为普通离线工具结果，不冒充REA Evidence。
- 工具第二次起强制本次会话logsrv入口校验，再发送固定16字节读取；没有任意地址参数。最终Boyi info成功，FW/idle/容量未变。
- [官方产物报告](../official-acquisition-followup.md)：精确远程页面配置、GET500、服务端包澄清、本地JADX加载壳证据；未获得官方固件。
- `just check` 格式/lint/语法及12个离线测试通过；包含入口变化拒绝路径。离线代码检查实跑并验证两份真实捕获一致。

## 第七轮：统一 uv CLI 的实机与安装验收

[验收摘要](cli-validation-2026-10-12.json)：`uv run comi verify --code`完整通过；实际录音start/pause/resume/stop均读回确认；新录音56912字节，导出大小吻合，ffprobe为MP3/16000Hz/单声道/14.228秒。sync补导出3个旧文件，同大小跳过新文件1个；明确size-only。

noise设置9→8→9，每次读回吻合；最后FW1.0.4、idle、容量59634/59632、noise9。测试录音保留在设备，音频只在本地忽略目录，无删除/重启/刷机。

wheel和sdist构建成功；Ubuntu运行wheel的doctor与两份实际代码样本比较成功，证明离线安装/入口/Thumb解码，未验证Linux蓝牙设备访问。42测试+22子测试通过，含真实帧、下载短读/断连/超量、原子保存、实时入口变化、重复采集不能冒充独立读取。

当前命令见[CLI](../cli.md)，包代码`src/rcominote`；旧tools脚本已迁入，源码/捕获证据仍独立于rlcdv。
