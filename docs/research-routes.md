# 当前研究路线

2026-10-14。此页只保留当前决策；[历史过程、淘汰细节及 SDK 定位](archive/research-routes-2026-10-13.md)已归档。原目标仍是：独立 CLI → 理解实际板级/固件 → 完整备份 → 可恢复运行 → 自写固件。

## 现在在哪

- **当前执行点**：[activity next4b原whole失败/首pair512接受](prefilled-factory-activity-next4b-live-2026-10-15.md)：仅1ed600完整pair新增512私有raw；1ed800 LE已连但21ATT/58HCI仅MTU-discovery，未应答FindInformation→reason08/errno110，零identity/baseline/Actions/RAM/NOR/SDwrite，后两页零I/O。总283ATT510HCI/15complete/0pending/status；原whole/page1false和parentgate拒绝保持。最后actualcurrent是page0second4096，identityUTC14日18:57:20.885464Z FW010004NOTEidle/unbound/charging100/free59589；失败后未SD重读。独立无HCI post-info不能补原after/whole。90plannednonce全reserved，与cohortmax72不同。实际FAST/no pulse，新DEFAULT集成/wake form未radio；新helper review不等于正式CP/plan/live。factory/carrier/sectorhash/hex/nonces私有，无binary，先commit/push后按交接独立检查接续，不自动retry。

- **已证明的参数对照**：[按下载窗口控制参数](download-window-live-2026-10-14.md)的只读真机试验通过：两次既有文件4096B各匹配独立oracle；startup外设FAST、两次host归一6/0/500、两次EOF外设SLOW全部结算，slow生效均晚于完整End。NOR适配实际观察到第二次归一前的FAST并等其完成，最新2400的完整窗口审计已通过；不证明物理worker退出或隐藏缓存清空。

- **后续按交接接续缺失2048B**：先commit/push，新helper检查/正式offlineCP/新fixedplan各自可复验后才能root有限执行；本轮失败whole仍拒绝，current来自acceptedpage0second/history90，不能用独立info补after。未新CP/plan/live；不自动retry/扩展/删除。aa5a capturedsource继承2786+159/351formatbuild/357inputs，新roothelper检查不混入旧捕获。[host吞吐审计](../artifacts/raw-export-throughput-host-review-20261015/evidence.json)理想81.16h/4MiB非ETA/binarybridge。用户仅报电源键和录音滑键；RESET/暴露可拔电池/独立ROMexit仍未证。[hidden scratch删除边界](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14)不授权删除。

- **覆盖库存与overlay**：[ASOF24200冻结库存](nor-backup-coverage-2026-10-14.md)A36112/B155204/available191316B不改；后来10页5120B及privatefactory6144B叠加后，当前强来源**47376B**、可用潜在**202580B**。System连续raw首6144`[24000,25800)`完整，剩余system raw备份未完；A原producer完整可重放，B仅历史manifest/checksum不升级，factory累计6144B完整pair、余2048B缺完整覆盖；DSPextra444B缺bytes不计。无mapped/reencoded/FF填补，跨历史捕获非全片原子快照。

- **已完成原始分区**：[fw1_boot完整4096B](final-boot-sector-live-2026-10-14.md)全部八地址来源重验、实际全FF，没有有效备用boot代码；未知块无独立字节oracle，历史失败保持。原始分区完成与scratch复用控制分别计量，完整4MiB NOR备份、恢复、自写固件硬件运行仍未完成。

- **规模化边界**：同文件复用已减少文件增长，但最新四页原任务保持失败；仍每次SD写4096B、NOR fread512B，不证明整片吞吐或长期可靠性。[较大binary出口有界审计](nor-binary-export-boundary-2026-10-14.md)未建立安全入口；`snort`实际先测速、再擦除/写入，禁止实测。禁止依赖已释放heap、任意MMIO、未证raw alias或ROM进入；不将已审入口结论外推为全镜像不存在其他路线。

- **原失败保持**：[旧early固定tail计划](backup-boot-tail-2026-10-14.md)首个2400第二读offline0B后停止；[首轮窗口2400](window-nor2400-live-2026-10-14.md)因composer行严格拒绝，second slow未结算/无第二barrier。两轮原件都失败、新覆盖各0；新成功是另一次完整实验，不能反推旧失败为成功。[2200成功](dual-unknown2200-2026-10-14.md)依旧有效，剩余未验范围不按FF推断。

- **完整备份主线的新现场依据**：[7.5ms/CE1策略](sd-interval-live-2026-10-14.md)完整RAM4096，[context→ring基线→boot0](sd-nor-interval-live-2026-10-14.md)、[已知4200独立双读/真实btmon早收尾](sd-nor-offset4200-live-2026-10-14.md)及上方单连接连续原型均通过。它们检验内容出口、偏移、重复性和连接复用，不增加已有raw覆盖。本次初始45ms且CE hints1/1，非纯interval单变量/历史15ms受控比较。[slot0两字](map0-entry-live-2026-10-14.md)为1000000f、00024000，仍不证明窗口尺寸或新raw alias；现有命令无SD文件range-copy/truncate，同名短dump保留旧尾。未知范围只按上方当前执行点推进。

- **板级真机推进**：[小文件Flash→SD→Boyi](live-board-tests-2026-10-13.md)已补守卫/上下文；历史ring基线3852B仍保持失败，新ring基线/boot0完整结果独立记录。[known-mdb16→slot→新SD512](logsrv-slot-live-2026-10-14.md)整体通过后，[GPIO28 CTRL首次LDR32实测](gpio28-word-live-2026-10-14.md)取得1805，counter206/slot6、nonce→55B行、完整下载/状态均通过。实际配置不同于早期4125，需结合已审后续writer解释；下一寄存器应按具体UART/SD板级问题选单项，不批量扩展。分段可变printk ring缺稳定快照合同，CPU/DMA切换也非可靠冻结锁。不重跑旧help/4KiB预热或批量NOR任务。

  已验证固定`dbg mdw 40068074 1`（GPIO28 CTRL）：[既有word代码证据](evidence/cpuid-word-read-code-2026-10-12.json)width=4、count以word计、实际`100251b0`执行LDR32、ASCII从栈副本生成、shell输出。现场另验`100a18ee/10`和`100251aa/24`；旧30B仅wrapper，**不含LDR32**。实际单word行55B（8位小写hex、31空格、4 ASCII、CRLF）。每轮必须新pointer/context与完整slot计数门槛；仍无硬件手册级read-clear或物理触点证明。

- **可用**：BLE 上位机，状态/录音/文件导出/部分设置已实测。[使用方法](cli.md)、[能力与验收](cli-capabilities.md)。
- **可复用**：实际系统、boot0、recovery、DSP、参数槽等已取得；部分 LARK 外设资料、匹配 M4 的最小镜像构建和局部 checker 仿真。[平台地图](device-platform-map.md)。
- **未完成**：完整物理 NOR 备份、原厂恢复、自写固件在设备运行。参考 SDK 构建和离线校验不替代这些验收。
- **当前不能提供**：Wi-Fi 快传、USB U 盘、CLI 切换 NOTE/CALL。前两项没有可用本机传输链；后一项只有读状态与手动按钮操作依据。
- **Linux已到达诊断通道，缺片已缩小范围**：[Ubuntu交接](ubuntu-handoff.md)。CID4 bind修正已真机通过LE/MTU247/服务发现；`help`仍缺244 B，且[HCI已缺该片](evidence/linux-log-hci-loss-2026-10-13.json)，不是Python解析器丢失。完整日志通道未验收；短读取加版本查询也在HCI缺24 B尾部，停止重复连接、help或短输出填充测试。
- **Linux普通CLI已可用**：[直接LE/Boyi验收](evidence/linux-boyi-cli-2026-10-13.json)完成状态、12项列表、240522 B既有文件导出及12s空闲watch；导出SHA256匹配此前Mac独立基线，前后完整状态/列表一致。修复普通连接选错bearer，不解除Actions日志或恢复约束。
- **Android第三主机已完成一次有界对照**：[完整HCI与回调](android-runtime-followup.md#2026-10-13第三主机与完整hci证据)均缺第二帧首244 B，全11条Actions通知与Linux HCI逐字节相同；独立结束info等于初始、NOTE/idle。已闭合实际固件“入队成功→异步HCI ring失败→释放包”的静态路径，尚无现场失败归因；下一步取发送现场/空口证据，不继续换主机重试help。无root抓包可用，不等于日志出口修复。

## 下一步：先解除什么约束

| 优先级 | 工作与作用 | 可以从哪里开始 / 完成标准 |
|---|---|---|
| 1 | 匹配板级、线缆与独立退出证据，决定 ROM/首次运行是否可试 | 精确型号/PCB 版本/芯片、原配四触点线数据接线、独立复位或断电方式。优先资料及可逆检查；拆机、短接、改线不是此清单自动授权的实验。形成可验证的接线/退出说明，而非“长按应该能恢复” |
| 2 | 匹配 ATS3085L/LARK M4 的 BSP、量产配置和官方恢复包 | 只跟进具体厂商包、开发板资料、源码分支或已取得的新链接；现有公开 M33 包和历史搜索已审。不再重复泛搜。拿到可识别版本/板型/依赖的实际材料才算进展 |
| 3 | 将材料转成一个可恢复的首次运行实验 | 先明确目标、进入方式、初始化影响和独立退出；ROM 枚举、RAM/helper 执行、NOR 写入分别验收。当前尚不满足执行条件 |

用户重新指定国内第三方分享后，[有界续查](domestic-sdk-followup-2026-10-13.md#renewed-domestic-pass-source-acquired-exact-older-lark-package-identified)取得两份Gitee Actions Android宿主源码，并从开发者原文确定旧LARK目标`SDK-TAG_ZS308A_2700_220112`/`ATS308x_zs308A`文档。新找到的221215同系列仓库已核实为空；没有匹配M4 BSP/恢复包。后续围绕实际包/ref/附件继续，不把Java上位机或2004年SDK30F手册当芯片层源码。

继续检查已取得maker材料，[内层封装与随包样例](production-package-contract.md#内层maker已解出的边界)已解出两种包头、FAT/XOR读取分支及43个文件；31项宿主清单名称/长度吻合。[host续查](host-selection-followup.md#2026-10-13-recovered-maker-host-conditional-default-now-identified)闭合条件式USBDevice→指定DLL→CClassical及31 B上传/切换包头；入口接收既有transport对象，没有CoMi选择链。样例为2 MiB/11项、三个helper与既有参考相同，芯片/板型/USB选择表为空，未取得匹配恢复包；到此停止扩展该样例callee。用户确认原配磁吸线接在本Ubuntu，无电气检测工具；整根线数据接线和独立退出仍未确认。

**新增官方材料优先于旧样例扩展。** [Actions测试盒/DUT/板级包](actions-official-tester-2026-10-13.md)已保存原始包、SHA和全部层级证据：测试盒ACTTEST0八成员CRC通过、type100、56个FAT输出、CRC有效板名ats3085c_bt_tester_128m、16 MiB/21项、完整71680 B recovery；与CoMi仅两段leaf函数精确相同。helper是不同的较早构建且仍有状态写路径；DUT helper为MIPS，不能混用。下一步可针对该完整官方recovery/新host中一个能改变进入、备份或退出决策的差异核对，主证据仍为实际CoMi镜像。原生PADS/BOM是测试板参考，未解CoMi接线/复位；不改变物理实验门槛。

没有新材料时，不用更多微小反汇编任务代替上述缺口。音频模式任务已完成一轮；后续只按实际用途选择：

- **音频静态链与实录样本已完成**：[NOTE/CALL实际模式、GPIO和gain](note-call-audio-2026-10-13.md)已定位；用户屏幕确认模式01/02，旧CLI标签已纠正。两模式各6s、手机外放CALL60s、听筒CALL约20s与NOTE约23s均已完整导出并验证MP3格式。听筒NOTE实时断连，重连确认仍录音并显式停止；不能记实时一致。听筒片段未严格同步，物理麦归属/可懂度/模式优劣仍未知；先试听或取得同片段对照需要，再增加声学实验。不继续逐callee扩展，不将本轮视为BSP/恢复门槛解除。
- **针对“听起来相似”的独立复核已收敛**：闭合BLE START→UI→launcher→producer静态路由，未发现选定路径强制同一模式；实际132项增益表匹配LARK SDK，NOTE/CALL请求36.5/40.5 dB，ADC字段不同。现场代码guard和一次旧诊断工具对照均日志帧失败，未启动录音或取得运行GPIO/ADC值。实验脚本保留在`experiments/`，不列入可用CLI；可靠读取通道恢复前暂停，不要求用户重复声学操作。
- **CLI导出测量已完成一轮**：Ubuntu既有一分钟录音240522 B、4.2746s、约55 KiB/s，完整长度/结束/hash与此前Mac基线通过；没有更长样本或实际吞吐需求时不重复下载。遇到新的实际失败才研究恢复；不因Boyi成功重开日志逐扇区路线。

## 封存路线与重新开启条件

| 路线 | 当前决定 | 何时重开 |
|---|---|---|
| Wi-Fi 快传/扩展功能 | 本机无线硬件和入口未证实；相关 Mova/3085S 命令不能移植；[精确型号记录](wifi-radio-model-2026-10-13.md)仅列蓝牙，原始认证待核 | 型号对应的官方 Wi-Fi 流程、无线模块/原始认证或匹配固件实现；不再重复 UI 字符串搜索 |
| 普通 USB U 盘 | 设置往返、on 后拔插都未枚举；[完整线材的数据接线未验证](usb-next-steps-2026-10-13.md) | 新线材接线/正常模式实现证据；不重复同线同接口的 toggle/replug |
| 旧 NOR 日志逐扇区批量导出 | 旧重连/全会话early策略退役，原件保留；新窗口策略已完成boot1全4KiB | 已验known复用及v2单24400/24600/24800；原24a失败保留；新v3已独立完成首4KiB；原known17失败/W0成功保持；新continuousv3/STATUS4均失败，actualSTATUSCONTENTcheckpoint0coverage后factory失败；变量byte须新方案，不靠常量mask，不靠重试延续旧任务 |
| 录音中GPIO/ADC日志读回 | [旧成功帧对照](log-buffer-wrap.md#2026-10-13另一种失败完整帧的首个ble分片缺失)确认首244 B分片缺失；Linux与Android独立HCI/全部回调重复同一缺口；实际异步TX失败链已静态闭合，尚无可靠运行态快照或现场归因 | 按[Android对照](android-runtime-followup.md)取得可区分候选的空口/设备发送证据；不重复换主机、短输出刷新、相邻callee扩展或猜测填字节 |
| 现有 M33 SDK 直接给 CoMi 刷写 | 板型/核/库不匹配；成功参考构建只证明工具链 | 匹配 LARK M4 BSP 或独立兼容性证据 |
| 原样加载 LARK helper/JLink loader | 初始化会改 NOR 状态/映射；SD loader 接口与本机不符 | 匹配且审清初始化、传输、边界、退出和错误处理的实现 |
| F5F0 OTA / ATT 请求当备份 | 已审方向是设备索取主机文件，不是导出本机 Flash | 新的实际设备到主机内容导出实现 |
| App 登录/远程网页、后台 JAR | 当前安卓无CoMi账号，官方页面不可进入；旧 URL 500，新版受保护；后台包未取得。独立安卓诊断工具已安装，不依赖登录 | 实际部署资源、新包或正常账号会话；不重试同一失效入口或绕过登录 |
| 任意 RAM 执行入口、ROM 盲探 | 已审正常模式未发现支持的执行合同；独立退出未建立 | 明确入口/可读范围与退出依据；不将内存写原语改成猜测执行 |

## 工作与证据规则

1. 每个任务先写一个会改变决策的问题，说明现有证据、验证方式和停止条件。
2. 优先复用固定镜像、源码和独立 oracle；真机用于只有真机能回答的问题。先识别设备，实验后核对原状态。
3. `ACK`、字段读回、物理效果、重启持久性、恢复成功分别表述。测试通过不是完整备份或可刷机证明。
4. 新结论先修正已有专题和入口；只有独立问题需要新报告。不以文件、脚本或 commit 数衡量进度。
5. 失效方法和错误产物归档并注明替代项；有效原始证据不因方法低效而删除。`artifacts/` 含私有录音/配置，不批量清理。
6. 纯入口/文案整理只做离线检查；不为证明文档修改而反复操作硬件。
