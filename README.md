# CoMi Note 固件研究

目标：理解致远 CoMi Note 的 SoC、板级资源、固件与 SDK，取得完整备份和可恢复的运行路径，随后开发自写固件。已有独立 BLE CLI；**尚不支持完整固件备份、刷写或原厂恢复**。

最新[activity next4b原whole失败/首pair512接受](docs/prefilled-factory-activity-next4b-live-2026-10-15.md)：仅1ed600完整pair新增512私有raw；1ed800 LE已连但21ATT/58HCI仅MTU-discovery，未应答FindInformation→reason08/errno110，零identity/baseline/Actions/RAM/NOR/SDwrite，后两页零I/O。总283ATT510HCI/15complete/0pending/status；原whole/page1false和parentgate拒绝保持。最后actualcurrent是page0second4096，identityUTC14日18:57:20.885464Z FW010004NOTEidle/unbound/charging100/free59589；失败后未SD重读。独立无HCI post-info不能补原after/whole。90plannednonce全reserved，与cohortmax72不同。实际FAST/no pulse，新DEFAULT集成/wake form未radio；新helper review不等于正式CP/plan/live。factory/carrier/sectorhash/hex/nonces私有，无binary，先commit/push后按交接独立检查接续，不自动retry。

此前[首个genericv2单24400](docs/paired-nor24400-live-2026-10-14.md)成功512B，后续四页job仅24600/24800完整pair新增1024B，24a first完整下载但旧strictprefix4095拒绝，second零命令、24c零I/O；旧失败未被新v3翻案。

[冻结覆盖库存](docs/nor-backup-coverage-2026-10-14.md)仍ASOF24200 A36112/B155204/潜在191316B；后续10页5120B加privatefactory6144B只作索引overlay，当前**强来源47376B、可用潜在202580B**。System连续首6144B raw`[24000,25800)`完整，剩余system raw备份未完成；B缺完整producer来源不升级，factory累计6144B完整双读、余2048B缺完整覆盖；DSP尾444B缺bytes不计，mapped/reencoded/FF填补不计raw。整片4MiB备份/恢复/自写固件运行未完成。

此前[bulk2048](docs/paired-nor25000-four-live-2026-10-14.md)、[首4KiB](docs/system-first4k-raw-live-2026-10-14.md)、[factory首pair512](docs/factory-first4-failed-2026-10-14.md)、[四页partial失败](docs/prefilled-factory-four-live-2026-10-15.md)及[ONE成功](docs/prefilled-factory-one-live-2026-10-15.md)原件保持。historicalONE仅IDENTITYONLY expected-state来源/current_owned_file_verified=False；[NEXT3失败](docs/prefilled-factory-next3-failed-2026-10-15.md)仍false；其observedownedSD经noticeCP5eb2/defaultCPf870零写链采纳，旧CP ASOF不改；本轮freshbaseline复读后新覆盖完成，page0second/current4096/history90已观察，失败whole仍未admitted。aa5a冻结153source140tests/293隔离文件一致；继承原checkwindow2786+159/56.73s、351format/lint/build、357declaredinputs不变，4a/4b均new_full_check_run=false；4b106snapshotmodules完整原capture重放，不替代root后续新helper检查。oldloss bursts实际45/45/60ms、均未applied6；此前RAMtrial有不同ap6/order/CEhints/output条件，只是一个knownRAM256控制成功，不证明唯一因果修复/长期可靠性/较大NOR出口/整片路线。CE1/1仅requestedhints，不当实测eventlength。Actions会改临时logRAM/sessionstate，但无explicitRAM/MMIO/NORwrite。后续有限范围须另fixedplan/sourcegate，保留history90；DEFAULT集成分支与新增wake form未实测，不自动retry/扩展/删除，历史失败不翻案。用户仅报电源键和录音滑键；RESET/暴露可拔电池/独立ROMexit仍未证。[hidden scratch删除边界](docs/file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14)不授权删除。

此前[系统24200固定双读](docs/system24200-live-2026-10-14.md)新增512B，既有32B reset解码完整匹配mapped向量页SP01002b40/reset1002d819；新24400至24e00各512/512匹配预声明mapped片段；assembled4096固定32reset解码也完整匹配mapped首4096。后验转换关系不参与raw验收，不证明efuse key、整system物理镜像或可恢复性。以下历史阶段的“下一步”不作为当前执行计划。

[最后2e00真机双读与完整分区](docs/final-boot-sector-live-2026-10-14.md)：独立新任务一次连接、两次producer，全部日志新鲜度/下载窗口/HCI/真实身份门槛通过；全部历史来源重验后保存`fw1_boot[0x2000,0x3000)`完整4096B，实际全FF、没有有效备用boot代码。未知块仍无独立字节oracle，不等于完整4MiB备份或可恢复。当时FW010004/NOTE/idle/charging100/free59589，新增两份scratch；随后[scratch复用试验](docs/scratch-reuse-live-2026-10-14.md)因缺uptime F0正文停止；[独立零写读回](docs/scratch-postmortem-live-2026-10-14.md)确认同一文件已保存新nonce和完整boot0已知内容。随后[同一文件recovery内容控制](docs/scratch-4200-live-2026-10-14.md)成功：先核当前文件，再覆盖与完整读回，匹配独立4200原件，零新增文件。原失败保持；复用减少文件增长，仍每次只提取512B NOR。

## 从这里读

1. [设备、固件与 SDK 总览](docs/device-platform-map.md)：已知平台、固件组成、可复用材料、关键缺口及暂存问题。
2. [当前研究路线与淘汰记录](docs/research-routes.md)：唯一执行优先级；历史报告的“下一步”不作为计划。
3. [CLI 使用说明](docs/cli.md)与[能力边界](docs/cli-capabilities.md)：可用命令、实测能力与未验证行为。
4. [证据索引](docs/evidence/README.md)：原始样本与复验；[历史路线](docs/archive/research-routes-2026-10-13.md)仅供溯源。

[Ubuntu 接手入口](docs/ubuntu-handoff.md)：Linux普通CLI已用直接LE连接完成状态/列表/既有录音导出验收；Actions日志仍在HCI缺片，后续门槛见交接记录。

[Android第三主机对照](docs/android-runtime-followup.md)：最小诊断工具已实测；无root
完整HCI确认同样缺244 B，11条通知与Linux HCI逐字节相同。状态复核通过，日志出口未修复。

[新增真机板级验证](docs/live-board-tests-2026-10-13.md)：七处代码守卫与实际printk上下文已取得；历史4KiB下载缺244B，[阶段收据](docs/evidence/sd-nor-progress-2026-10-14/README.md)保留失败边界。[新7.5ms/CE1连接策略](docs/sd-interval-live-2026-10-14.md)完整下载既有RAM4096B；随后[新ring基线及boot0对照](docs/sd-nor-interval-live-2026-10-14.md)完整通过，原始NOR512B匹配独立oracle。后续非零偏移与未知地址双读见下；整片备份、恢复未完成。

[logsrv运行上下文](docs/logsrv-context-live-2026-10-14.md)：另一套日志服务的实际指针与32B上下文已完整读回；rd=wr=204、一个槽长度139。该次采样只取得元数据，不把长度字段当新鲜日志内容。

[已知短读取经日志槽导出](docs/logsrv-slot-live-2026-10-14.md)：随后一次固定mdb16实测通过；本次随机标记之后完整代码行与独立镜像匹配，新的512B槽文件完整下载，7ACK/F1及状态检查通过。不是整片NOR或一般可靠性证明。

[GPIO28控制字真机读回](docs/gpio28-word-live-2026-10-14.md)：首次对齐32位读取完整通过，观测`0x00001805`；UART0功能字段仍为5，但电气配置与早期`0x4125`不同。未测物理触点、电压或UART输出。

[slot0映射配置真机读回](docs/map0-entry-live-2026-10-14.md)：两个独立word为`1000000f`、`00024000`，支持当前系统映射的物理起点24000及CRC属性bit31清零。不证明窗口大小、raw alias或整片NOR可读。

[原始NOR非零偏移独立双读](docs/sd-nor-offset4200-live-2026-10-14.md)：两次offset4200读取均匹配已有recovery原始oracle，参数/状态/独立性复验通过；真实btmon可正常提前收尾。验证偏移与重复性，不增加既有覆盖。[早期boot1/2200重连方法](docs/backup-boot-block1-2026-10-14.md)留下单份完整512B，双读未完成；原失败保留。

[单连接连续NOR导出真机通过](docs/dual-known-nor-live-2026-10-14.md)：boot0与4200各512B匹配独立oracle，验证连续读取与连接复用。[未知0x2200独立双读随后成功](docs/dual-unknown2200-2026-10-14.md)：early6/0/500策略下两份完整环、严格当前日志链、148 ATT/HCI及真实barrier通过，512B全相等；无独立字节oracle，新增已配对覆盖512B。此前失败保留；该轮与既有2000前缀形成前1024/4096B，未读部分不按全FF推断。

[备份boot剩余区间固定计划](docs/backup-boot-tail-2026-10-14.md)：六个地址预先固定、最多十二次读取，首个2400第二读遇额外参数请求即停止；第一份完整但未配对，后五地址未执行，新验证覆盖0。实包证明early更新耗时可变、短连接仍会跨入外设协商窗口。

[按下载窗口控制参数的真机试验](docs/download-window-live-2026-10-14.md)随后通过：同一既有RAM文件两次完整4096B均匹配独立oracle；五次参数事务全部结算，每次归一6/0/500后下载，EOF慢速更新均在完整End之后生效。零新增SD文件、零新增原始NOR覆盖；下一步将此合同适配到有界NOR双读，不重跑旧early计划。

[新窗口策略下的首轮2400双读](docs/window-nor2400-live-2026-10-14.md)：两份4096B日志完整，第二份插入异步`composer: post fps 2`，严格解析拒绝，原pair保持失败。

[限定composer语法后的新2400双读成功](docs/window-nor2400-composer-2026-10-14.md)：两次独立producer/nonce、完整日志、六次参数结算、严格新鲜度/previous-dump锚及真实状态barrier全通过；第二份实际出现已定位的33B显示计数日志，仅允许这一完整行于指定间隙。新增已配对原始覆盖512B，该轮累计前1536/4096B；当时剩余五扇区未知，尚无完整NOR备份或恢复证明。

[五扇区窗口任务的真机结果](docs/window-boot-tail-live-2026-10-14.md)：2600独立双读完整通过，已配对前缀增至2048/4096B；2800两份完整候选因额外状态广播未纳入审计而拒绝，任务保持失败、后三地址未执行、无完整分区输出。下一轮采用显式异步事件账本和独立最新状态checkpoint，固定剩余四地址；旧失败不改判。

[新四地址任务的真机结果](docs/status-boot-tail-live-2026-10-14.md)：新2800完整独立双读通过，当时前缀为2560/4096B；2a00连接建立后在GATT发现阶段监督超时，无producer或SD写，任务停止。该成功连接实际状态事件为0，不能当作事件插入路径的真机验证。随后一次[只读健康检查](docs/status-link-health-2026-10-14.md)通过，完整GATT/身份/HCI及正常本地断连均取得、状态59590不变；下一轮固定剩余2a00/2c00/2e00，全三对与既有来源验收后才装配4KiB。

[剩余三地址任务的启动参数边界](docs/status-remaining-live-2026-10-14.md)：首地址在任何Actions前遇到完整远端24..40/0/500→实际36的事务，固定FAST门槛拒绝；完整GATT与前后身份保持59590，零producer/SD写/新增覆盖。当前优先核实际默认参数选择，并做既有RAM文件的只读DEFAULT→FAST对照；不原样重跑该任务。

[默认参数与日志活动的实际固件路径](docs/ble-default-parameter-path-2026-10-14.md)已闭合：初始已快可使应用更新no-op清pending，延后worker采用default表；日志控制发送可安排FAST，但必须实测完整事务，不能从ACK推断。[同scratch复用候选](docs/nor-scratch-reuse-plan.md)当时另核独立nonce与4096B覆盖写；后续复用实测见上方最新结果，仍不减少SD写次数。

[DEFAULT→FAST已知内容真机对照](docs/startup-ram-default-live-2026-10-14.md)随后通过：seed实际FAST并正常断开；新连接实际DEFAULT后，两次日志控制活动之后均取得完整FAST、host6/0/500、4096B独立oracle下载、EOF SLOW和真实身份barrier。两个连接全ATT/HCI及正常断连复验通过；零新SD文件/NOR覆盖，当时仍前2560/4096B。只证明请求排序，未追踪隐藏延迟队列的唯一触发源；下一步将显式分支接入剩余三地址双读。

[受控三地址任务的新真机结果](docs/startup-boot-tail-live-2026-10-14.md)：2a00/2c00完整独立双读通过，该轮新增1024B→前3584/4096B；2e00在特性交换阶段失败、尚无ATT/producer/SD写，原job失败无fullbin。两成功NOR连接实际均为FAST启动，不冒充NOR DEFAULT分支实测。[本机内核错误映射](docs/linux-le-features-error-2026-10-14.md)解释HCI status3e为何变成errno38，无线原因仍未知。当时剩余仅2e00；后续独立任务见下。

[随附说明书核对](docs/manual-2026-10-13.md)：模拟硅麦+骨传导麦、NOTE/CALL、
电源按键与录音滑键、磁吸充电口；照片与校验值已归档。尚不能确定精确麦克风颗数或独立复位方法。

[USB文件传输研究](docs/usb-next-steps-2026-10-13.md)：CLI能读NOTE/CALL、不能切换；
USB配置往返及on后拔插均未出现新USB接口。原配整根磁吸线的数据接线仍待确认。

[Wi-Fi研究结论](docs/wifi-capability-2026-10-13.md)：未找到本机可用的Wi-Fi传输链；
参考SDK依赖外接芯片，相关App协议与本机不同。当前不提供Wi-Fi快传，等待新硬件或官方功能证据。

## 当前认识（2026-10-14）

| 主题 | 结论与边界 |
|---|---|
| 平台 | [实机CPUID](docs/cpu-identity.md)为Cortex-M4 r0p1；[固件板名](docs/firmware-board-identity.md)为 `ats3085l_dvb_watch_ext_nor_max`；实体SoC丝印仍未知 |
| SDK | 公开SDK的M33参考板已在Ubuntu构建；不能作为CoMi固件。[LARK材料](docs/lark-helper-candidate.md)更接近M4，但缺完整BSP |
| 新官方参考 | [ATS3085C测试盒固件与原生板资料](docs/actions-official-tester-2026-10-13.md)已保存固定hash；完整恢复镜像可对照，但16 MiB/21项板型不是CoMi，DUT helper另为MIPS |
| 存储 | [18项ACPT配置覆盖4 MiB NOR](docs/partition-readback.md)；[录音SD路径](docs/card-state-readback.md)独立，容量约64 GB |
| 已取得固件 | [备用boot原始4KiB](docs/final-boot-sector-live-2026-10-14.md)全FF；完整[927632 B系统映射镜像](docs/offline-system-analysis.md)、[boot0](docs/boot-complete.md)、[110148 B录音DSP](docs/record-dsp-export.md)、分区表；[recovery完整63,288 B](docs/recovery-complete.md)校验通过；[param双槽原始各4KiB](docs/param-slots.md)，主槽有效、备用槽全FF；[factory-RW历史8KiB私有备份记录](docs/factory-rw-backup.md)记载12条记录CRC通过，当前raw缺失待重采；来源完整性分层见上方库存。不是整片原始备份 |
| 恢复/刷写 | 已分析[实际boot](docs/actual-boot-flow.md)、[ROM下载入口](docs/actual-rom-adfu-entry.md)、[OTA容器](docs/ota-container-contract.md)；无匹配官方恢复包、实测ROM传输或恢复证明 |
| 自写镜像 | [最小M4 ELF与948 B ACTH镜像](docs/minimal-firmware-image.md)可重复构建，通过本机recovery真实checker离线仿真；未在硬件运行 |
| USB | 原配磁吸线设置/拔插对照未发现CoMi枚举；整根线的数据能力未验证，ROM模式未试 |
| 客户端 | 固定官方App的[23个请求opcode均有主机路径](docs/remaining-client-contracts.md)，不等于全部实机验收。BLE状态、录音控制、文件下载、部分配置已实测；[短窗口实时流与离线MP3逐字节相同](docs/realtime-live.md)，不保证长时无丢失 |

下一步核心依赖是匹配BSP/生产包、板级与独立退出证据；没有新入口时不重复泛搜。
[NOTE/CALL音频核对](docs/note-call-audio-2026-10-13.md)已确认软件模式、启动路由及不同ADC增益配置；
现场GPIO/ADC读回因日志完整性失败暂挂，尚不能确认实际拾音器切换。它不替代恢复条件。
[当前路线与停止条件](docs/research-routes.md)。

## 使用 CLI

```sh
uv sync --all-extras
uv run comi --help
uv run comi scan
uv run comi info
uv run comi files
uv run comi record start
uv run comi record stop
uv run comi download NAME --out artifacts/recordings
uv run comi settings show
uv run comi watch --duration 5
uv run comi diag capture platform --out artifacts/platform-NEW.json
```

包在 `src/rcominote/`。JSON输出，错误非零退出，按序列号选设备；下载校验完整长度后原子保存，拒绝覆盖。下载／同步中Ctrl-C保留标注不完整的文件和元数据，断开连接、退出130。诊断只开放固定profile，没有任意shell、刷机或恢复命令。

[实际CLI取消验证](docs/download-cancel-contract.md#actual-cli-sigint-validation-2026-10-13)：真机上一次SIGINT保存4,416 B正确前缀、退出130；新连接完整下载与指定偏移下载均逐字节符合旧完整基线，设备状态及7项录音列表不变。不是自动续传或设备线程退出证明。

macOS需蓝牙权限，官方App先断开；Linux需本机BlueZ/适配器。APK、SDK、原始录音、完整日志在忽略的 `artifacts/`；仓库不依赖rlcdv、Obsidian或临时交接文件。

显式单文件删除见[CLI说明](docs/cli.md)：必填serial和文件名确认；已用新建且双下载留存的测试录音实机验收，删除后列表恢复原状，不证明安全擦除。`maintenance`提供绑定／解绑／格式化／恢复出厂／手机类型的显式请求；退出3表示提交但效果未验证，没有实机执行这些管理操作。

目录用途：`src/rcominote/`为CLI，`tools/`为资料获取和离线分析，`firmware/`为最小镜像/参考定义；
`docs/`保留专题结论，`docs/evidence/`保存可复验证据。`docs/archive/`和`src/rcominote/archive/`保留历史或退役方法，
不作为默认执行入口。私有录音、配置与大型下载在忽略的`artifacts/`中，不批量删除。

## 开发与参考构建

```sh
just                 # 仅列出 recipes
just check           # 格式、lint、shell语法、离线测试
uv build
```

Linux x86_64参考板构建，不打包或刷写CoMi：

```sh
bash tools/setup_sdk.sh
uv run --locked tools/build_sdk.py \
  --sdk "$HOME/w/_tmp/lv_port_actions_technology" \
  --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" \
  --out artifacts/sdk-build --jobs 4
```

[SDK源码定位](docs/actions-sdk.md) · [参考构建实测](docs/ubuntu-build.md) · [烧录/恢复评估](docs/flash-recovery-assessment.md) · [BLE协议](docs/protocol.md) · [官方后台参考](docs/seeyon-backend-reference.md)。旧脚本命令对应历史提交，现用命令以CLI文档为准。
