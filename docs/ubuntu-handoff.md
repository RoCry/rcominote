# Ubuntu 接手：CoMi 真机研究

更新至2026-10-14。仓库`~/w/_hw/rcominote`，分支`main`。保持原目标：实用CLI、实际硬件/固件/SDK理解、完整NOR备份、可靠恢复、自写固件运行；后三项仍未完成。先读本页，再按需查[当前路线](research-routes.md)和[平台地图](device-platform-map.md)，不要重做历史泛搜。

**最新执行点：next4b失败，只接受首pair512**：[activity next4b原whole失败/首pair512接受](prefilled-factory-activity-next4b-live-2026-10-15.md)：仅1ed600完整pair新增512私有raw；1ed800 LE已连但21ATT/58HCI仅MTU-discovery，未应答FindInformation→reason08/errno110，零identity/baseline/Actions/RAM/NOR/SDwrite，后两页零I/O。总283ATT510HCI/15complete/0pending/status；原whole/page1false和parentgate拒绝保持。最后actualcurrent是page0second4096，identityUTC14日18:57:20.885464Z FW010004NOTEidle/unbound/charging100/free59589；失败后未SD重读。独立无HCI post-info不能补原after/whole。90plannednonce全reserved，与cohortmax72不同。实际FAST/no pulse，新DEFAULT集成/wake form未radio；新helper review不等于正式CP/plan/live。factory/carrier/sectorhash/hex/nonces私有，无binary，先commit/push后按交接独立检查接续，不自动retry。

**旧失败与离线checkpoint分开**：[四页v2原job](paired-nor-system4-live-2026-10-14.md)仅246/248两pair新增1024B，失败24a first/wholejob仍false、原strictprefix拒绝可重放，second零命令、24c零I/O。新offlinecommunicationcheckpoint只采纳原failedfirst完整4096/六参数/全wire/真实59589状态，host-only/0设备I/O/0新NOR覆盖；新v3baseline完整匹配该文件后才执行新两producer。此成功不是对旧候选重新解析补判。此前[单24400 v2](paired-nor24400-live-2026-10-14.md)512B成功也独立保留。

**实际current来自accepted页，失败whole未admitted**：4b page0second完整4096为最新actualowned对象，lastidentity18:57:20.885464Z/free59589；failedpage仅discovery无写，后两页无I/O。独立post-info无HCI/未SD读回，不能补原after或修复whole。90nonce全plannedreserved，cohortmax72另计；需正式hostcheckpoint+新plan再接续，不把helper reviewed当执行成功。aa5a153source140tests/293files，继承2786+159/351formatlint/build/357inputs，next4b未新fullcheck；新root代码检查另计。

**覆盖叠加，冻结库存不改**：[ASOF24200库存](nor-backup-coverage-2026-10-14.md)A36112/B155204/潜在191316B，加后来10页5120B及privatefactory6144B overlay，当前A强来源**47376B**、A+B可用潜在**202580B**。System连续raw首6144B`[24000,25800)`已全，余下system raw备份未完；B来源不完整不升级，factory8KiB累计6144B完整pair/余2048B缺完整覆盖，DSPextra444B仍缺raw，不能跳过采集或补mapped/reencoded/FF。完整4MiB备份/恢复/自写固件仍未完成。

**后续按交接独立接续**：先commit/push，再对新helper固定source/checkpoint/仅缺失范围新plan逐项审计；未正式新CP/plan/live，不自动retry、盲批整片、heapprobe、outputmodechange或删除。actualFAST分支成功不证明DEFAULT集成或wake新form。用户仅报电源键和录音滑键；RESET/暴露可拔电池/独立ROMexit仍未证。[hidden scratch删除静态边界](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14)不授权删除/绕过visible-list守卫。下方历史不当当前计划。[host吞吐审计](../artifacts/raw-export-throughput-host-review-20261015/evidence.json)理想81.16h/4MiB非ETA/binarybridge。

**历史boot1完成点**：[最后2e00独立双读](final-boot-sector-live-2026-10-14.md)真机成功，148ATT/255HCI、六完整参数事务/0pending/0status、startup实际FAST，两个freshproducer/各完整4096环/512B、全部freshness/window/state/HCI通过。120源码冻结，1641回归+159subtests/build；全部3584旧来源/control/新pair重验才保存完整`fw1_boot[2000,3000)`4096B，实际全FF/SHAf47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6，无有效备用boot代码。未知块无独立字节oracle，完整4MiB备份/恢复/自写固件仍未完成。当时真实final.after FW010004/NOTE/idle/unbound/charging/battery100/free59589；first写0MiB、second写降1MiB，末次只读barrier不变。Ubuntu70已下载+1旧声明+1历史可能=max72，未删除。原受控3地址job/2e特性交换失败保持，[HCI3e→errno38解释](linux-le-features-error-2026-10-14.md)不证明无线原因已修复。

**只读参数对照仍成功**：[两次既有RAM4096](download-window-live-2026-10-14.md)root与独立agent完整replay通过，各自匹配独立oracle；startup FAST、两次host归一、两次EOF SLOW共五次事务完整结算，slow生效均晚于完整End。该轮无新增SD文件/NOR覆盖；新NOR第二份解析失败不否定该独立对照。

**此前同一scratch已知4200控制成功**：[单次覆写控制](scratch-4200-live-2026-10-14.md)先完整读取并匹配[postmortem当前boot0文件](scratch-postmortem-live-2026-10-14.md)3621…0360，再一个freshnonce/known4200 producer/同长同文件覆盖/完整下载。136ATT/243HCI/六完整参数/0pending/0status、6ACK/F1/F0=0、独立4200oracle与strictnonce/prefix4096全过；producer→dump实际一条exact33B composer。新ring SHA10bd351c52d1d8560ad28929b9d8b34002ebe8398586bdf988595dc0d3f433e1，仍4096B；当时设备文件已不是3621或原a2f7 baseline，现又被24200及上方后续试验覆盖。131source+104tests冻结/1886+159/build，完整归档replay通过；latest真实59589/NOTEidle/charging100不变、normaldisconnect16、1现有文件覆盖/0新文件、cohort70+1+1=max72。已分别观察同路径boot0与4200更新，旧6ACK/0F0失败不翻案、原两cover九事务试验仍失败、0unique NOR增量。随后24200、24400及24600/24800完整配对已完成；最新24a00失败与当前对象见上方。24000旧44窗口/32行双覆盖已重放匹配512B，24200 mapped向量预期不当raw oracle；不直接批量、不读释放heap、不进ROM/写NOR。用户只有power与recordslider，独立退出/磁吸data wiring仍缺。

**首轮新窗口失败仍保留**：[原2400 pair](window-nor2400-live-2026-10-14.md)虽两份4096完整，但second composer插入使旧严格grammar拒绝，未等slow2/未完成second barrier；5complete+1pending、141ATT/245HCI、34件原版本snapshot固定。后续仅window模式启用exact33B notice，并将decode移至slow/identity后；旧默认proof不变、新失败原件不能改判。

**原tail任务失败保持**：[固定备份boot tail计划](backup-boot-tail-2026-10-14.md)首个2400 pair失败即停止：first4096/512/真实barrier/HCI通过，second已请求且收到4096声明但offline0B；后五无producer。early归一耗时1.903370s，第二声明在connect+4.970179s，外设slow在5.015178s出现却未完成Update；短连接不足以避开。job/pair原件仍失败，新验证覆盖0，无完整分区输出。独立后续health不能替代失败after。

**历史覆盖来源保持**：[未知0x2200独立双读](dual-unknown2200-2026-10-14.md)成功仍可完整replay，两份512B全FF相等，无独立字节oracle。该次与既有2000前缀构成前1024B；上方新2400增加至1536B。早期成功只证明该次有界时序，不为新失败提供oracle或免检。

**失败与成功分开**：[早期重连方法](backup-boot-block1-2026-10-14.md)first下载ENOSYS、first-b单份完整、second零写失败保持原判。新dual首轮同样失败：CTRL_EVENT→ACL RX时间戳-100µs触发旧全局单调规则，同时EOF slow导致第二参数请求，不能仅修parser改判。后续新earlytrial在initial identity前明确归一6/0/500，baseline48/4/600原样保留，全epoch仅一个参数请求；与实际Android fast表匹配，可能在deferred请求前完成。观测connect→lastATT4.282762s，非连接已关闭时长；时序机制不等于规模化可靠性保证。两轮原件和源码快照分别保留。

**已实施新鲜度门槛**：`nor_freshness.parse_ring`要求最近精确producer/status、32连续canonical行和真实20B prefix；第二份mandatory上一dump锚，缺失/覆盖/错序即失败。synthetic失败反例及四份已知完整ring回放通过；第二份真实previous marker环绕区间已验。每个operation_id独立目录/nonce；只有最终identity/state/HCI audit完成后允许全512比较。旧generic parser留作历史，未知读取不使用它。

**既有证据可复验**：[四份实际fullring](dual-known-nor-live-2026-10-14.md)经新freshness规则仍匹配各自独立oracle；无旧成功翻案。历史`hci_interval.py`SHA3120…d9保留，旧public/private收据继续通过；新`hci_monitor.Snoop`保留原戳/顺序，分别约束门控事件与ACL方向流，不强制CTRL_EVENT与RX全局单调。`Monitor`可显式选现代parser。known双目标原型源码6件、新failed10件、新early成功12件均各有private source-snapshot。

**最新原始NOR对照**：[新context28→ring基线4096→boot0](sd-nor-interval-live-2026-10-14.md)各阶段完整通过；boot0原始512B SHA72952…7ec匹配独立oracle，5ACK/F1、唯一完整marker/status/连续32行、下载区间HCI和结束状态通过。首次context发现阶段ERR110零写保留，context-b为独立新采样。新增三份SD文件，累计45；无NOR/MMIO写、ROM进入或新代码运行。下一步先解决55s抓包收尾，再有界验证已知非零偏移双读，不自动扩展未知NOR。

**更新：非零offset4200双读完成**：`artifacts/nor-sd-offset4200-20261014/{first,second}`分别新producer/SD文件/连接，完整4096环及原始512B SHA51327…713匹配完整recovery-raw[512:1024]；`sd_nor_targets.verify_pair`重放全链/独立性通过。真实btmon均SIGINT sent/exit0早收尾，final HCI参数门槛通过、前后状态59593一致。新增两文件，累计47。boot1 offset2000首512已有全FF双覆盖oracle；下一缺失目标为同4KiB分区内2200，不把2000重读算新增覆盖。

**传输前置**：[7.5ms/CE1策略](sd-interval-live-2026-10-14.md)完整下载既有RAM4096B，SHA35437a…d7b与独立oracle一致，HCI整个下载区间门槛通过、前后free59593及其他状态一致。原stdinEOF认证失败在任何设备I/O之前；独立新目录b为首实际硬件试验。该只读前置没有新SD文件或Actions/NOR写。三个完整传输的btmon均已按55s超时退出。

**最新映射现场**：[slot0两个独立单word](map0-entry-live-2026-10-14.md)为CPUword1000000f、offsetword00024000；分别counter208/slot0和210/slot2、完整Actions/文件/nonce/最终状态通过。offset首份ctx后置ENOSYS保持失败，另采ctx-b通过。无MMIO/NOR写或新alias探测。

**最新单寄存器现场**：[GPIO28 CTRL](gpio28-word-live-2026-10-14.md)首次实际mdw读取为`00001805`，counter206/slot6，新nonce/完整55B行及4/32/512B文件、7ACK/F1、前后完整info一致。free59595MiB，FW010004/NOTE/idle/charging；SD测试文件累计31。此前服务发现超时未发送Actions，另一次错误路径在离线拒绝；原报告保留，未重读GPIO。未测物理针脚/UART电气；下文更早阶段的文件计数与“未GPIO读取”仅对应当时实验。

**后续现场进展**：[logsrv已知短读→slot→新SD512](logsrv-slot-live-2026-10-14.md)唯一一次真机整体通过，4/32/512B完整下载，7ACK/F1及当前状态检查成功。独立随机done标记之后完整mdb16代码行匹配既有oracle。最新info为FW010004/NOTE/idle/charging、free59595MiB；截至该实验共24个非音频SD测试文件保留。没有GPIO/MMIO读取或刷写；完整NOR/恢复未完成。下段free59597/12文件是更早的14日快照。

**2026-10-14最新现场覆盖下文早期快照**：[新增真机验证](live-board-tests-2026-10-13.md)七处守卫与printk上下文已取得；尾512B完整匹配，但末次info失败，原报告仍失败。4096B预热和ring基线均仅3852B，未执行boot/NOR阶段。后来独立info为FW010004/NOTE/idle/charging、free59597MiB。两轮十二份SD测试文件保留，无固件写/ROM进入。用户确认只有电源键、录音滑键；独立退出未建立。`rg`当前可用。下文“仅发现/MTU”及旧Mac状态是早期历史，不当当前状态；所有本轮btmon均已结束。[最新收据](evidence/sd-nor-progress-2026-10-14/README.md)。

## 接手范围与现场

- Ubuntu本地负责下一轮Linux BLE/HCI验证；接手前确认Mac会话没有同时连接CoMi。不要让两个agent竞争硬件。
- 设备序列号`C261CF0430`、public MAC `50:C0:F0:AE:7C:0E`、广告名`CoMi Note 2F01`、既有FW010004；始终按广告序列号选中，不凭名称选首个设备。
- 用户最初说距离PC约3m，随后明确已将卡放在Linux主机旁边。最后一次应用状态来自前轮Mac：NOTE/idle；本轮仅连接、服务发现及MTU通信，没有录音/模式/配置/固件写入。下次需重新观察状态，不把旧状态当当前证明。
- Linux：BlueZ5.72，kernel6.14.0-36-generic，hci0 Intel适配器。`btmon`、`gatttool`可用；`rg`未安装，Ubuntu可用`grep`。uv管理的Python缺`socket.AF_BLUETOOTH`，新实验用已核对Linux ABI的ctypes bind/connect。
- 本轮所有`btmon`均有timeout，已结束；没有后台录音或待收尾的连接。未重启服务、改全局ControllerMode、配对、删除缓存或升级系统软件。

## 为什么旧Linux路径失败

[HCI/源码摘要](evidence/linux-le-hci-2026-10-13.json)。完整抓包含周边设备，留在Ubuntu和Mac忽略目录`artifacts/log-hci-2026-10-13/`，不要整包公开。

1. 普通`uv run comi info`经Bleak→BlueZ Device1.Connect，**实际发BR/EDR Create Connection 0x0405**，随后Page Timeout0x04。CoMi广告flags02未声明BR/EDR不支持；BlueZ5.72将两个bearer时间同时更新，平局优先BR/EDR。不是已经证明的CLI线协议超时。
2. 5.72 `bluetoothctl connect`没有`le`参数；`ConnectProfile`也不能强制LE。实验性Adapter1.ConnectDevice未在现有daemon暴露。不为本任务重启全机蓝牙或擅改配置。
3. `gatttool -t public --primary`明确发LE 0x2043。原位置RSSI−88，初步连接后remote-features/断连reason0x3e，未到ATT。靠近后RSSI−76，收到GAP/GATT/Battery、Actions、F5F0、E5E0服务回复。
4. 靠近试验中，设备主动发MTU请求`02f700`；gatttool回复`0102000006`（不支持），设备又回复对ErrorResponse的ErrorResponse。工具报Unlikely Error，**却退出0**。因此不能用exit0验收。`-m247`在该版LE路径不解决此问题，交互主动MTU也不等于支持对端请求。

固定BlueZ源码commit `770ad5614e7e8074133e6f563495ce4822f63fe4`；地址选择[adapter.c](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/src/adapter.c#L7272)、[device.c](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/src/device.c#L2480)，[GATT server MTU oracle](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/src/shared/gatt-server.c#L1502)。

## Ubuntu普通CLI已修复并验收

继续接手时用户确认Mac/官方App已断开；没有新增嗅探器、BSP或板级信息。原配磁吸线仍接着，数据能力未证。与Astra审查后，优先修复已证实的普通CLI连接缺陷，不重跑日志实验。

- `Connection`在Linux使用`linux_att.py`/`linux_client.py`：扫描按serial选择，要求public地址，明确LE/CID4连接、双方MTU处理，分页发现并校验Boyi服务/特征/CCCD。沿用原有Boyi CRC、事务、下载长度和取消逻辑；macOS仍走Bleak。
- 生产通道不保存全量ATT，取消旧实验4096 PDU总量限制；通知队列有界，空闲等待无10s截止，溢出/损坏/断连失败传播。不自动重试、重连、配对或改BlueZ全局配置。
- [实机验收收据](evidence/linux-boyi-cli-2026-10-13.json)：`info`、12项完整`files`成功；已有240522 B录音导出4.2746s、56268 B/s，SHA256与此前Mac独立完整下载/实时样本一致；MP3完整解码通过。`watch --duration 12`成功、无事件；随后新连接完整info/列表均等于初始，NOTE/idle/charging。音频与完整列表留`artifacts/linux-boyi-cli/`。
- 离线覆盖Linux发现/分流/断连/请求超时/取消STOP；本次未实测Linux录音、设置、管理、实时流或物理Ctrl-C。单文件不能代表长期无丢包。
- `comi gatt`和Actions诊断仍用各自原路径；**Boyi成功不修复Actions日志缺片**。原目标的整片NOR、原厂恢复、自写固件运行仍缺证据。

## 修正版真机结果与下一步

`860a73a`的CID4 bind修正已于03:28 UTC真机复验：LE连接、双方MTU247、完整服务发现、Actions特征/CCCD均成功。随后`help`仍缺第二个512 B帧的首244 B；**HCI已经缺片**，不再怀疑Python拼帧丢掉这一片。[逐字节收据](evidence/linux-log-hci-loss-2026-10-13.json)。

- HCI #552–554等于独立旧成功帧1；#555–556等于帧2的`[244:488]`、`[488:512]`。没有`[0:244]`。
- HCI共11个日志通知；socket记录9个，与HCI前9个逐字节相同；解码器只消费7个。严格解析失败后STOP清理仍读同一个坏stream，再失败并关闭socket。
- HCI仍有完整帧3、help ACK、STOP ACK、F1。报告`ack_count=2/end_received=false`不是设备没发ACK/END的证明。原始捕获在两机`artifacts/linux-att-bind-check/`，所有进程已结束，无录音/配置/固件写入。
- 没有空口抓包，不能断言设备固件一定是根因；尚不能区分设备发送/控制器、无线链路、主机控制器/驱动。Mac与Linux同样缺片削弱了单一宿主上层错误的解释。

离线复验（无需硬件）：

```sh
uv run tools/verify_linux_log_capture.py artifacts/linux-att-bind-check
```

下一轮不要原样重跑`help`或重查BlueZ连接。若继续独立定位：失败后原始ATT收集现保留0.5 s窗口，本次全部ACK/F1已收；这不是任意链路的结束保证。保留原始失败判定，禁止重同步/补造。只有已具备BLE空口嗅探硬件时，再同步一次空口与HCI，判断缺片是否真正发送/确认；不假定现场已有嗅探器。

短输出替代已做一次，**未通过，不原样重试**：`f873545`的`linux_log --short-read`读取固定`1000ab40`16 B，逐条`kernel version`填充、上限8次；第6次时日志到达，但首512 B帧只有244+244 B，随后出现完整55 B新帧，缺24 B尾部。HCI与socket全部14通知逐字节一致，含最后ACK/F1。[完整实验收据](evidence/linux-short-read-2026-10-13.json)。目标行在原始不完整帧中可见，严格校验拒绝成功；没有去读GPIO/ADC、启动录音或扩展地址。

此方法复用旧`nor_batch.py`，依据是504 B缓冲满才推进wr；8次是历史经验上限，非理论保证。结果表明避开`help`仍不足以恢复可靠读取，不能把它升级为正式CLI能力。下一步须有新变量/证据（如同步空口抓包或实际设备发送链定位），否则回到板级/匹配M4 BSP/恢复资料主线。需要HCI时继续用有界`sudo timeout --signal=INT 60s btmon -i 0 -w NEW.btsnoop`，不常驻，不覆盖旧证据。

## 不能丢的其他结论

- 用户重新要求国内第三方代码获取：[续查收据](evidence/domestic-sdk-renewed-2026-10-13.json)/[材料分类](domestic-sdk-followup-2026-10-13.md#renewed-domestic-pass-source-acquired-exact-older-lark-package-identified)。两份Gitee Actions Android SDK源码已克隆并固定版本；新精确LARK目标为`SDK-TAG_ZS308A_2700_220112`及`ATS308x_zs308A`应用文档。同系列221215仓库为空、SDK30F附件属2004年Z80，不能当匹配BSP；目前仍未取得M4芯片层整包。没有因此重开日志/ROM实验。
- [精确上传者补查](evidence/domestic-sdk-owner-followup-2026-10-13.json)已覆盖全部303公开仓库、相关Zephyr/VG-Lite fork及7个匿名7z附件；附件目录均为GPCV6248相机SDK，未取得匹配M4包。此上传者的已记录入口无需再从头枚举；新包/ref/下载链接或板级退出证据到来后继续主线。
- [日志缺片复验](log-buffer-wrap.md)：Mac失败捕获相对独立旧成功帧缺首244 B，后268 B完全匹配；不是解析器误切，也不能只用封帧前ring丢文本解释。Linux已缩小到HCI观察点之前，仍不能把SDK潜在bug直接当本机根因。
- [NOTE/CALL](note-call-audio-2026-10-13.md)：模式/文件枚举已真机纠正；选定BLE START不强制同模式；132项增益表与LARK SDK匹配，请求36.5/40.5 dB，ADC字段不同。运行GPIO/ADC和物理拾音器切换仍未读回，用户说听起来相近。
- 完整系统、boot0、recovery、DSP及部分配置已取得；**不是完整4MiB原始NOR备份**。无可靠原厂恢复、ROM独立退出或自写固件上机证明。不要为了进度盲进ROM、执行helper或刷写。
- USB原配线数据接线未证，普通模式未枚举；Wi-Fi没有本机链路证据。旧NOR逐扇区日志路线已退役，未先证明可靠性/吞吐改善就不重开。

改动后`just check`、`uv build`，按真实结果更新现有报告再commit/push。Ubuntu接手后它是本阶段代码/证据的权威工作树；Mac只fast-forward同步，避免两边修改同一功能。
