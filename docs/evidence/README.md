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

## 第八轮：沿实机指令读取常量与函数名

[首次](code-references-first-2026-10-12.json)、[独立重读](code-references-second-2026-10-12.json)、[离线分析](code-references-analysis-2026-10-12.json)：五处共69 B一致，实际读到`_logsrv_init\0`，支持公开SDK源码对应。完整推导及未知见[报告](../code-reference-followup.md)。CLI新增固定code-literals/code-references及离线比较；传输完成与读回完整分别校验，丢正文不能再报代码读取成功。

原厂公开helper新增[命令/指令证据](helper-command-map-2026-10-12.json)与[静态报告](../helper-static-followup.md)：确认rm/rs处理器和NAND首次读取的延迟初始化，未在CoMi加载或执行。[Ubuntu离线反编译](../offline-helper-analysis.md)已运行并保存可复现脚本。

后续[初始化审计](../helper-initialization-decompile.md)证明延迟初始化有可达的条件擦除/编程路径；27函数导出可复现。[OEM官方APK调查](../oem-protocol-lead.md)取得独立App产物，确认固件元数据POST与AOTA/MD5/CRC路径，但没有CoMi镜像或跨设备适配证明。固件API未调用；CoMi登录调查按用户要求暂缓。

[vendor/OTA源码审计](../vendor-service-followup.md)：排除将`vendor_read`和OTA backend `.read`误认作设备固件导出；记录通知订阅可能触发OTA状态的完整调用链。未操作这些设备服务。

## 第九轮：实机vendor接收代码

[首次](vendor-code-first-2026-10-12.json)、[重读](vendor-code-second-2026-10-12.json)、[合并解码](vendor-code-analysis-2026-10-12.json)：380 B一致，实机`vendor_read`检查D22D帧头，接收payload后调用1000b3b4；不同于公开SDK上传解析器。完整推导与限制见[报告](../vendor-code-readback.md)。未向F5F0发送命令；[App产物定界搜索](../f5f0-artifact-search.md)未找到它的handler。

## 第十轮：实机命令分发表与BT_NAME路径

[首次](vendor-handler-first-2026-10-12.json)、[重读](vendor-handler-second-2026-10-12.json)、[分析](vendor-handler-analysis-2026-10-12.json)：580 B一致，包含已有32 B校验点；新增548 B，累计997个不同映射字节。58项TBB表中24个非默认命令，23个与官方App请求编号对应；`3a`路径引用`BT_NAME`。[报告](../vendor-dispatch-followup.md)。

两项实际失败均保留：[入口短日志未刷出](vendor-handler-buffered-entry-2026-10-12.json)导致guard超时、未发送后续读取；[长突发丢失b504行](vendor-handler-lost-row-2026-10-12.json)虽ACK/结束帧完整仍失败。新profile在依赖guard前刷出短日志；每四行后刷出并等待本批完整数据，避免继续积压。最终两个会话56 ACK、正文完整。此方法不是任意长度dump性能或可靠性保证。

[配置只读查询](vendor-bt-name-query-2026-10-12.json)：`BT_NAME`与`BT_LE_NAME`均返回14 B `CoMi Note 2F01`；`FW_VERION`仍失败。没有执行`3a`或改名。最终Boyi状态FW010004、idle、容量59634/59632、noise9；未重启/刷写。

## 第十一轮：设备信息与容量来源

[首次](device-info-first-2026-10-12.json)、[重读](device-info-second-2026-10-12.json)、[分析](device-info-analysis-2026-10-12.json)：601 B一致，包含已有112 B，新增489 B，累计1486个不同映射字节。两个会话均59 ACK、结束帧/正文完整。实际容量查询参数`/SD:`，版本常量`010004`，模型串`xink_test`；完整容量算术与字段来源见[报告](../device-info-fields.md)。仅证明文件系统卷容量，不是物理存储或固件分区备份。

[存储诊断候选审计](../storage-diagnostic-candidates.md)发现部分看似日志/只读路径可能flush存储，未执行；[VTOR审计](../vector-base-read-audit.md)确认架构地址与对齐32位读取要求，但实机特权/核心仍未完全确认，未读取该寄存器。CoMi App登录按用户要求暂缓。

[结束状态](device-info-final-state-2026-10-12.json)：FW010004、idle、容量59634/59632、noise9；未重启/刷写。`just check`通过56测试+24子测试，wheel/sdist构建通过。

## 第十二轮：从卷名到实际FAT容量回调

[首次](storage-first-2026-10-12.json)、[重读](storage-second-2026-10-12.json)、[分析](storage-analysis-2026-10-12.json)：937 B完整一致，其中336 B新增，累计1822个不同映射字节（含40 B挂载RAM元数据）。证实实际VFS通过mount+1c→vtable+44间接调用，定位`/SD:`挂载对象与callback `100a42d7`，成功分支按512逻辑扇区和FAT簇计算统计。[完整报告](../storage-binding-readback.md)。

没有取得底层芯片ID、固件分区表或完整备份。RAM两次相同只是会话快照，不代表原子冻结或重启后仍有效。新增指针变化阻止继续解引用的测试；`just check`通过58测试+24子测试，wheel/sdist构建成功。没有执行新的文件系统操作或写入。

[结束状态](storage-final-state-2026-10-12.json)：FW010004、idle、容量59634/59632、noise9，设备正常响应。

## 第十三轮：exFAT簇、磁盘registry与MMC_1

[首次](disk-first-2026-10-12.json)、[重读](disk-second-2026-10-12.json)、[分析](disk-analysis-2026-10-12.json)：1487 B一致，新增550 B，累计2372不同映射字节。查到exFAT type4/drive4、128 KiB簇、有效空闲簇缓存、唯一名为SD的disk_info；状态callback引用设备`sd`，其配置名和控制器对象均为`MMC_1`。[实机报告](../disk-registry-readback.md)；[卡元数据/分区路线源码审计](../sd-metadata-candidates.md)。

`disk_metadata`复算59634/59632 MiB，与独立[结束状态](disk-final-state-2026-10-12.json)相同；FW010004、idle、noise9。无新内部函数调用、重启或刷写；不能把所有容量查询概括为物理上无写，缓存失效路径的源码边界已记录。60测试+24子测试通过，wheel/sdist构建成功。

## SD/MMC状态与卡类别

[首次](card-first-2026-10-12.json)、[重读](card-second-2026-10-12.json)、[分析](card-analysis-2026-10-12.json)：2031 B一致，新增544 B，累计2916不同映射字节。实际指令定位driver状态，type=0与SD枚举/低功耗类型分支吻合；512 B、122138624扇区与disk_info一致。控制器配置base常量40058000；未访问MMIO。[报告](../card-state-readback.md)、[结束状态](card-final-state-2026-10-12.json)。

## 独立Flash对象与device表

[首次](boot-first-2026-10-12.json)、[重读](boot-second-2026-10-12.json)、[分析](boot-analysis-2026-10-12.json)：2931 B一致；新增867不同映射字节，累计3783 B。31项设备表含spi_flash、sim_flash、CDC_ACM；spi_flash ready、布局配置32 MiB，尚未验证JEDEC ID或启动来源。[报告](../boot-storage-device-readback.md)、[结束状态](boot-final-state-2026-10-12.json)。

## NOR缓存ID与配置容量差异

[首次](nor-first-2026-10-12.json)、[重读](nor-second-2026-10-12.json)、[分析](nor-analysis-2026-10-12.json)：3101 B一致，新增170 B，累计3953不同映射字节。缓存ID16405e、flags0；Zbit原厂32 Mbit系列资料与ID相符，不能把driver32 MiB配置视作物理容量。[报告](../nor-driver-readback.md)、[原厂来源](zbit-id-sources-2026-10-12.json)、[结束状态](nor-final-state-2026-10-12.json)。

## 日志服务回调与协议入口

[首次](shell-first-2026-10-12.json)、[重读](shell-second-2026-10-12.json)、[分析](shell-analysis-2026-10-12.json)：345 B一致，新增276 B，累计4229不同映射字节。实际timer callback存储与协议头检查已确认；尚未到shell表或分区表。[报告](../shell-service-readback.md)、[结束状态](shell-final-state-2026-10-12.json)。

## TLV文本到shell执行入口

[首次](shell-text-first-2026-10-12.json)、[重读](shell-text-second-2026-10-12.json)、[分析](shell-text-analysis-2026-10-12.json)：777 B一致，新增432 B，累计4661不同映射字节。文本type1到shell execute及内部执行callee已定位；命令表未读。[报告](../shell-text-readback.md)、[结束状态](shell-text-final-state-2026-10-12.json)。

## shell registry与dbg静态表

[首次](shell-registry-first-2026-10-12.json)、[重读](shell-registry-second-2026-10-12.json)、[分析](shell-registry-analysis-2026-10-12.json)：1535 B一致，新增758 B，累计5419不同映射字节。13项root registry、dbg descriptor及静态子命令数组指针已确认；子命令数组未读。[报告](../shell-registry-readback.md)、[结束状态](shell-registry-final-state-2026-10-12.json)。

## 实机ACPT分区表

[首次](partition-first-2026-10-12.json)、[重读](partition-second-2026-10-12.json)、[分析](partition-analysis-2026-10-12.json)：2987 B一致，新增1452 B，累计6871不同映射字节。完整744 B ACPT缓存表CRC703f5674，18项NOR配置覆盖4 MiB；不等于原始Flash镜像。[报告](../partition-readback.md)、[结束状态](partition-final-state-2026-10-12.json)。

## 启动安全标志源码审计

[固定SDK来源摘录与原文件SHA256](boot-security-source-audit-2026-10-12.json)、[解释及实机边界](../boot-security-source-audit.md)。无新增设备I/O；区分ACPT加密声明、镜像签名路径、CRC映射和OTA写标志。

## 启动SRAM候选交叉核对

[首次](boot-info-first-2026-10-12.json)、[重读](boot-info-second-2026-10-12.json)、[分析](boot-info-analysis-2026-10-12.json)：3051 B一致，新增64 B，累计6935不同映射字节。SDK-layout候选的param_save/system/nor字段匹配实机ACPT，param_phy=0不匹配；不等于完整ABI证明。[报告](../boot-info-readback.md)、[结束状态](boot-info-final-state-2026-10-12.json)。
