# CoMi Note 固件前期研究

目标：确认手上这台致远 CoMi Note 的芯片、板级资源、备份与恢复路径，随后尝试自写固件。当前有独立可用的 BLE 工具和研究资料，**尚无可刷写的 CoMi 固件或经验证的恢复方式**。

## 当前结论（2026-10-12）

| 问题 | 已知与边界 |
|---|---|
| 设备 | 自有 `C261CF0430`，广播 `CoMi Note 2F01`，固件 `1.0.4`；包装样本型号 `SY-N2A3F-5H2` 尚需和实机底标核对 |
| 平台 | GATT 与 Actions（炬芯）SDK 的日志服务匹配，固定 PREPARE/ACK 也已实测相容；具体 SoC、板号仍未知 |
| 数据通路 | Boyi BLE 协议已验证，状态/列表/下载不需绑定；既往实测录音为 16 kHz 单声道、32 kbps MP3 |
| 新鲜实机证据 | 本轮重新枚举 GATT、读取状态；MTU 247，4 个服务，普通模式未见 Actions OTA UUID，`usb_mode=true` |
| USB | 用户确认数据线后做拔插对照，仍未见明确 CoMi 枚举；`usb_mode=true` 不等于主机数据接口已启用，板级走线/其他模式待查 |
| 日志/shell | 实机执行 `kernel version` 返回 Zephyr 2.7.0；`help`/`dbg` 列出存储读取与 ADFU 重启命令，后者未执行 |
| 配置读回 | `dbg nvram BT_LE_NAME` 已返回14字节实机内容；原始 flash 正文仍未通过 BLE 取得 |
| 映射字节读回 | 已核对代码/运行元数据并开始系统正文断点导出，已追到exFAT→SD磁盘→sd后端→MMC_1；实际驱动状态支持SD协议；另定位ready的spi_flash对象，缓存ID匹配Zbit 4 MiB系列，驱动配置32 MiB不代表物理容量；已取得CRC通过的744 B缓存ACPT表、18项配置覆盖4 MiB；尚无完整固件/物理分区备份 |
| 自定义固件 | Actions 有构建、OTA、ADFU 等参考代码，也有签名/安全启动配置；CoMi 是否接受自签/未签名镜像尚未知 |
| Linux 构建 | Ubuntu 上参考板 hello_world 已生成 ELF/BIN/HEX；SDK 无源码补丁，构建后 tracked 文件干净；尚不是 CoMi 固件 |

## 阅读顺序

1. [固件研究路线与待解问题](docs/firmware-roadmap.md)：哪些证据决定下一步。
2. [Actions SDK 核查](docs/actions-sdk.md)：平台、构建、分区、升级、恢复及源码定位。
3. [App 升级与 USB 线索](docs/app-upgrade.md)：Boyi/Mova 区分、APK 固定样本与可复核提取。
4. [BLE 协议与工具](docs/protocol.md)：帧格式、命令、已有实机验证边界。
5. [证据来源与本轮验证](docs/evidence/README.md)：历史资料与新采集分开记录。
6. [USB 对照与日志握手](docs/usb-log-probe.md)：第二轮实机结果、复现工具。
7. [USB/ADFU 恢复传输](docs/recovery-transport.md)：RAM helper、ROM/DFU 区别、旧 host 兼容边界。
8. [固定 SDK 构建可行性](docs/build-feasibility.md)：Linux 编译候选配方、Python 2/x86 打包依赖与缺失物。
9. [Ubuntu 实测构建](docs/ubuntu-build.md)：已跑通的一键准备/编译、产物与已知限制。
10. [不拆机诊断](docs/noninvasive-diagnostics.md)：默认日志和只读 shell 候选，包含 ACK/短缓冲陷阱。

11. [烧录、失败恢复与提取评估](docs/flash-recovery-assessment.md)：四个问题、恢复占位代码与完整备份条件。
12. [实机诊断](docs/device-diagnostics.md)：已执行 shell、命令清单及有限读取结果。

13. [读回通路与下一阶段](docs/next-investigation.md)：当前能推进什么、每一步需要什么新证据。

14. [实机代码读回](docs/mapped-code-readback.md)：16字节独立重读一致、Thumb解码、实时入口检查和长输出丢失。
15. [原厂helper静态分析](docs/helper-static-followup.md)：rm/rs处理器、存储初始化边界；[Ubuntu反编译工具](docs/offline-helper-analysis.md)。
15. [官方产物继续核查](docs/official-acquisition-followup.md)：远程页面配置、发布包与加固壳边界。

## 统一 uv CLI

```sh
uv sync --all-extras
uv run comi --help
uv run comi scan
uv run comi info
uv run comi files
uv run comi record start              # 明确开始录音；stop/pause/resume 同理
uv run comi download NAME --out artifacts/recordings
uv run comi settings show
uv run comi diag capture platform --out artifacts/platform.json
uv run comi verify --code --out artifacts/verification-NEW
```

[完整使用说明](docs/cli.md) · [命令协议与支持边界](docs/cli-capabilities.md)。在仓库根目录使用 `uv run comi`，由uv管理项目环境。

包代码在 `src/rcominote/`；采集工具已统一迁入，不再维护独立 `tools/comi.py` 等副本。JSON输出，错误非零退出；按序列号选设备。下载校验完整长度后原子保存，拒绝覆盖。诊断只开放固定profile，代码读取限定经当前入口/指令/常量核对的固定位置；[69字节引用分析](docs/code-reference-followup.md)、[380字节vendor代码](docs/vendor-code-readback.md)、[命令分发表](docs/vendor-dispatch-followup.md)。没有刷机、任意shell、完整固件备份或恢复命令。

实机已验证录音start/pause/resume/stop、完整导出/sync、noise设置读回与恢复，以及一键只读诊断。其他setter源于固定App源码、按设备读回决定成功；时钟设置无已知getter，不能宣称回读验证。

macOS宿主需有蓝牙权限，官方App先断开；Linux需要本机BlueZ/适配器。APK/SDK/原始录音/完整日志放忽略的`artifacts/`；不依赖rlcdv、Obsidian或临时交接文件。

开发：`just check`；打包：`uv build`。Linux参考板准备与构建直接调用独立脚本：

```sh
bash tools/setup_sdk.sh
uv run --locked tools/build_sdk.py \
  --sdk "$HOME/w/_tmp/lv_port_actions_technology" \
  --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" \
  --out artifacts/sdk-build --jobs 4
```

仅Linux x86_64参考板编译，不打包或刷写CoMi。旧研究记录中的脚本命令对应其历史提交，当前命令以[CLI说明](docs/cli.md)为准。

`card-code`继续追踪SD/MMC驱动的固定代码与状态引用；两份采集用`uv run comi diag compare-references FIRST SECOND --card --out REPORT`离线核对。[驱动状态证据](docs/card-state-readback.md)。不调用存储操作或读取控制器寄存器。

[独立Flash对象与设备表](docs/boot-storage-device-readback.md)：31个设备名字，SPI Flash配置/实际RAM read wrapper；[分区表下一条引用路线](docs/partition-reference-route.md)。

[NOR缓存ID与容量差异](docs/nor-driver-readback.md)：实读`0x16405e`，对应Zbit 32 Mbit系列线索；版本/封装仍未知；分区表见下文。

[日志服务回调与协议入口](docs/shell-service-readback.md)：独立核对345 B，确认callback注册与`1d/81/10`检查；后续命令表和分区表成果见下文。

[文本命令到shell执行入口](docs/shell-text-readback.md)：777 B独立一致，已定位文本分支、backend getter与shell内部执行入口，命令表后续定位见下文。

[实机shell registry与dbg静态表](docs/shell-registry-readback.md)：确认13项root表，沿`dbg\0`找到静态子命令数组`100bb8d4`；实际`fread`身份与输出分流见[后续报告](docs/raw-read-handler-followup.md)。

[实际ACPT分区表](docs/partition-readback.md)：744 B两次一致且CRC通过，18项NOR分区覆盖4 MiB；含recovery、system、NVRAM及OTA临时区。加密标志与恢复机制仍需核对。

[启动SRAM候选](docs/boot-info-readback.md)：64 B独立一致，system/nor offset24000匹配ACPT；param物理字段为0，不强行套用完整SDK ABI。

[实际映射镜像头](docs/image-header-readback.md)：512 B头部校验通过且reset向量匹配，声明正文927120 B；flags/TLV长度均0，正文现已完整校验；raw Flash仍未取得。

[512 B多行读取验证](docs/header-batch-readback.md)：`uv run comi diag capture header-batch --out ...`，固定重读已知镜像头并逐行/hash验收；尚非正文导出。

[固定映射镜像导出](docs/mapped-image-export.md)：四块正文独立复读一致，跨进程续读已验证；256/512 B请求均捕获过截断。新增`uv run comi image export`断点读取与最终checksum门槛，已完成全正文校验；不等于原始Flash备份或可恢复。

[日志缓冲计数器回绕](docs/log-buffer-wrap.md)：实机Thumb指令确认8位计数器相减后的无符号比较缺陷；64 B正文与头部分段已实测，完整映射镜像现已导出，头/正文校验通过，见[验收](docs/evidence/mapped-system-complete-2026-10-12.json)。

[实机reset入口与C启动边界](docs/reset-entry-readback.md)：头部/向量指定的入口已解码，取得启动PSP、RAM向量地址、FPU与IRQ初始化常量；[后续启动调用](docs/startup-memory-readback.md)已解析两段清零、三段复制参数及kernel启动顺序；不据此推断ROM/签名/恢复能力。

[系统镜像离线分析](docs/offline-system-analysis.md)：新增无设备连接的`comi image inspect`及Ubuntu Ghidra入口；927632 B实机映射镜像导出与离线checksum验收通过；仍非raw NOR/整机恢复备份。

[printk实际backend](docs/printk-backend-readback.md)：fread正文走独立DMA分派或动态字符hook；已定位当前RAM flags/hook的最小读取目标，尚未实测其运行时值。

[启动反编译边界](docs/startup-noreturn-model.md)：具体thread-abort调用点no-return建模，Ubuntu完整镜像21入口重跑通过；修正literal伪控制流，仍保留参数推断限制。

[Console运行时实测](docs/printk-runtime-state.md)：新增`diag capture printk-state`和`diag inspect-printk`；两次固定10 B RAM一致，init=1/panic=0对应DMA分支，当前hook与启动载荷不同；尚未观察物理输出或原始Flash数据。

[原始映射缺口审计](docs/mapping-candidate-audit.md)：完整镜像中限定搜索未建立raw NOR换算依据；[35项实机dbg目录](docs/actual-dbg-command-inventory.md)检查遗漏返回路径，实际长度/副作用以handler证据为准。

[实机初始化与音频入口](docs/init-audio-board-evidence.md)：71项初始化表定位31个设备，audio_in明确绑定ADC_0；[显示板级证据](docs/display-board-evidence.md)：CH1115驱动标签、72×40配置、I2C_0/0x3c与GPIOA24/25，物理身份及完整初始化时序仍待验证。

[实际屏幕命令序列](docs/display-command-sequence.md)：28字节初始化表、GPIO逻辑复位顺序、条件AF命令及五页×72字节fill路径；等待单位和电气极性尚未核实。

[像素提交与页转换](docs/display-pixel-path.md)：实际u16非零→垂直页bit转换、窗口限制、旧descriptor ABI差异及buffer地址alias转换；尚无实屏验收。

[屏幕GPIO极性](docs/display-gpio-polarity.md)：init实际设置pin24反转、pin25不反转，已对应到set/reset寄存器写入；未测物理电压，等待单位仍未知。

[屏幕等待时间基准](docs/display-timebase.md)：实机代码每tick 32,000周期，busy-wait配置支持32 MHz，故10/120tick名义对应10/120 ms；未测调度延迟或引脚波形。

[屏幕I2C速率](docs/display-i2c-config.md)：实际configure将14映射到400 kHz目标、divider5；默认init为100 kHz，SDA/SCL pinmux仍待定位。

[实机早期pinmux表](docs/board-pinmux-evidence.md)：三张表25项，GPIO14/15的3808配置支持I2C0候选；SCL/SDA身份与物理连线仍待确认。

[像素指令仿真](docs/display-pixel-path.md#实际指令仿真验收)：`uv run tools/verify_display_pixels.py artifacts/mapped-system/mapped-system.bin`，固定镜像SHA；五组手工golden/失败序列验证实际Thumb callback，外部I2C/分配调用被拦截，无硬件I/O。

[音频open与板级输入映射](docs/audio-open-path.md)：实际ADC分支、宽度约束与7项输入映射表；尚未取得录音调用者的真实参数，不能推定麦克风数量/类型。

[录音参数适配层](docs/audio-parameter-adapter.md)：实际adapter固定16-bit、ADC key按stream type选择，采样率来自上层调用参数；仍未确认录音应用具体值。

[ABTP测试的16 kHz路径](docs/audio-fixed-rate-path.md)：实际命令7161→type1→rate16、stream5→ADC key4000、adapter16-bit；普通录音配置与ABTP可达性仍未知。

[音频适配层指令仿真](docs/audio-parameter-adapter.md#指令仿真验证字段搬运)：`uv run tools/verify_audio_adapter.py artifacts/mapped-system/mapped-system.bin`，验证字段搬运、固定width0和拒绝非ADC通道；48 kHz仅为测试输入。

[非ABTP媒体捕获配置](docs/recorder-media-config.md)：实际producer设置输入/输出16 kHz、16-bit、单声道，format1/bitrate32与SDK MP3/32 kbps对应；尚未以实际文件或运行状态验收。

[编码输出stream分支](docs/recorder-stream-path.md)：同步文件write与异步ring消费者；后者后端未定。

[实际codec分派](docs/recorder-codec-dispatch.md)：format1编码方向选择`mp3e`硬件记录、`aeRECORD.dsp`及DSP路径；支持MP3配置判断。DSP资源导出与加载执行仍未验证。

[DSP资源路径](docs/dsp-resource-path.md)：实际拼接`/NOR:K/aeRECORD.dsp`，K对应ACPT的`sdfs_k`分区（704 KiB）；尚未读取目录/文件，现有system导出未证明覆盖该资源。

[SDFS NOR读取](docs/sdfs-nor-read-path.md)：目录相对offset加分区offset，经Flash API读取。原始指令模拟确认读失败与EOF均返回0；未来导出必须核对预期长度。

[DSP文件加载器](docs/dsp-file-loader.md)：540 B头部、`xhqy`磁盘魔数与分段读取；指令模拟确认空sections可通过、初始seek错误未检查，不能以加载器成功替代备份完整性验证。

[录音下载路径](docs/recording-download-path.md)：实际拼接`/SD:/RECORDER/Call-或Note-<name>.mp3`，不是绝对路径文件接口，不能直接用于NOR DSP资源导出。

[应用ADFU重启路径](docs/application-reboot-path.md)：实际写重启标记并触发watchdog；尚不证明应用损坏后的独立恢复。当前优先级与证据缺口见[研究清单](docs/next-investigation.md)。

[USB_COPY设置](docs/usb-copy-setting.md)：实际0x13只在handler中更新配置并flush；ACK不携带flush失败，状态位不是USB枚举证明。连接事件与实际USB后端仍待核对。

[实际CDC配置](docs/usb-cdc-config.md)：10d6:b00a、CDC控制/数据interface与FS/HS端点，已模拟验证初始化注册顺序；不是实机枚举、ADFU或NOR导出证明。

[CDC启动与测试协议](docs/usb-cdc-startup.md)：测试标志→事件门→CDC线程，等待DTR后处理自定义命令；已确认部分命令写TEST_ITEM，不能作为只读shell直接探测。

[CDC命令表](docs/usb-cdc-command-map.md)：固定身份字段、状态查询、模式重启与SD格式化路径；默认命令也写TEST_ITEM，未建立固件/DSP导出能力。
