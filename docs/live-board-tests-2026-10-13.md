# 新板级结论的真机验证

更新至2026-10-14；C261CF0430 / FW010004。**已在真机验证小块映射 Flash→SD→Boyi 导出，并取得七处代码守卫与实际printk上下文。完整 NOR 备份、烧录、恢复及自写固件上机仍未完成。**

最新：[7.5ms/CE1连接策略](archive/sd-interval-live-2026-10-14.md)完整RAM4096B；随后[新context→ring基线→boot0对照](archive/sd-nor-interval-live-2026-10-14.md)分别通过，原始NOR512B匹配独立oracle。下文3852B记录保留为此前失败历史；非零偏移、独立双读与整片覆盖仍待新策略验收。

## 已执行

| 实验 | 真实结果 | 结论边界 |
|---|---|---|
| Boyi info | NOTE/idle、charging、FW010004 | 当前身份/状态；不证明恢复能力 |
| ATT MTU128，固定16B旧代码守卫 | 双向协商成功，512B日志帧仅收到387B；HCI与socket逐字节一致 | 降MTU未恢复读取；没有继续GPIO命令 |
| 固定 RAM `18000000` /4096B→SD | Actions 4ACK、F1、空pending；下载3852/4096B失败 | 留下一个SD文件；未验证整个文件，失败时部分数据尚未落盘 |
| 同一文件 offset3968 /128B | 新连接只读；完整下载、与独立RAM初值尾部完全一致 | 仅128B窗口；不与失败3852B拼接 |
| XIP `10000000` /32B→SD，两份独立文件 | 两次完整Actions与Boyi、32B逐字节匹配原镜像 | 小块映射表示可读；不是raw NOR或≥512B证明 |
| XIP `10024a20` /160B→SD | Actions完整；首次下载连接失败。之后只读同一文件成功，160B完全匹配 | 覆盖完整dumpbuf handler及literal；原失败报告保留，不改判成功 |

另两次连接在实验开始前失败 `ENOSYS`，没有SD写；没有无限重试。handler文件只读续验按原报告SHA绑定，没有重新创建文件。成功采样前后的完整device info相同。原始报告包含私人录音列表，保留在ignored `artifacts/live-*`；公开收据去掉该列表。

本轮留下**四个非音频SD测试文件**：RAM4096、两份header32、handler160。未删除。未发送NOR写入、重启、ROM进入、helper执行、录音或GPIO配置更改命令。尚无本轮GPIO/SD运行寄存器值、实际电气pinout或UART输出测量。

[公开实测收据](evidence/sd-bootstrap-2026-10-13.json)及[小样本原始字节/复验](evidence/sd-bootstrap-2026-10-13/README.md)覆盖全部八份SD报告，保留成功、连接失败和短下载失败；不将失败父会话的后续下载补验冒充原会话成功。

## 为什么小块XIP值得测

[固定实际固件证据](evidence/comi-file-write-2026-10-13.json)：`dumpbuf→fs_write→f_write` 在扇区边界区分长度。≥512B路径直接传源指针给disk_write；<512B路径通过明确的CPU `LDRB/STRB`循环复制到RAM文件缓存，再刷SD。两个32B文件的实测支持小块路径可用，**不能据此认定旧4096B全零就是DMA限制导致**。

代码观察、文件导出和物理Flash仍需分别证明。当前160B匹配只验证该次导出的handler范围，不代替fread、printk ring及其运行上下文的守卫。

## 复现

固定源profile，无自由地址/长度。每次新建随机短路径；console命令含换行≤63B。`--create-sd-file`明确创建并保留SD文件；先核对单次结果再继续，不以循环批量试错。

```sh
uv run -m rcominote.experiments.sd_bootstrap SYSTEM NEW_RAM --create-sd-file
uv run -m rcominote.experiments.sd_bootstrap SYSTEM NEW_TAIL --tail-report NEW_RAM/report.json
uv run -m rcominote.experiments.sd_bootstrap SYSTEM NEW_HEADER --source header --create-sd-file
uv run -m rcominote.experiments.sd_bootstrap SYSTEM NEW_HANDLER --source handler --create-sd-file
```

若完整Actions已证明文件写入请求完成，但随后的连接失败，可新建输出目录只读同一固定源文件；原报告保持失败：

```sh
uv run -m rcominote.experiments.sd_bootstrap SYSTEM NEW_READ --source handler --existing-report NEW_HANDLER/report.json
```

SYSTEM固定SHA为`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。成功要求完整Actions（或绑定完整父会话）、完整Boyi长度/终止、独立oracle逐字节匹配、前后状态。残缺流不得重同步、补片或当成功。当前工具保留后续下载失败的实际接收字节，并分开记录原始错误和后置查询错误。

MTU实验的[独立HCI收据](evidence/linux-mtu128-2026-10-13.json)明确区分STOP意图与wire：该次超时关闭连接后STOP未实际发送，无F1；不能把报告writes列表当发送证明。

## 接续

七处守卫已补齐，见下节。大文件Boyi传输仍会缺片；尾部offset只到EOF，不是任意长度读取。完整备份需要证明可靠大传输或有效分段合同，不能以大量小文件、零散代码窗口或失败文件拼接替代。ROM进入仍缺独立退出与真实接线证据；用户确认实物只有电源键、录音滑键。

## 2026-10-14：守卫、上下文与512B边界

[公开收据及字节复验](evidence/sd-nor-progress-2026-10-14/README.md)保留失败判定；原始完整会话、HCI和录音列表留在ignored目录。

| 实验 | 真实结果 | 边界 |
|---|---|---|
| 七处XIP守卫，共412B | 新增五处220B，结合旧header32/handler160；实际字节均匹配固定system | 覆盖fread、printk hook/ring/描述符；不是NOR读回 |
| printk context `1800e008` /28B | 完整Actions和下载；r=w=1698、used=0、capacity=4096、buffer=`1803ee09`、init=1、panic=0 | 最后info连接失败；后置独立info通过的派生报告仍使用历史28B，不是新快照 |
| ring baseline4096 | Actions完整，下载仅3852B | 基线不完整，未执行后续boot0/NOR producer |
| 同一旧RAM文件：先尾128B，再全4096B | 尾部完整匹配，状态查询屏障通过；全文件仍3852B | 已知RAM oracle唯一缺口`[756,1000)`；未补造或拼接 |
| 同一旧RAM文件：尾512B | 完整512B及结束标记，独立oracle逐字节匹配 | 最后info失败，整体报告保持失败；不能推广成所有512B传输可靠 |
| 后续独立info | NOTE/idle、charging、FW010004；与上述实验前状态相同 | 单独状态观察，不改写失败会话 |

新增八个SD测试文件，连同上一轮四个共十二个，均保留。一次小文件写入使整数MiB空闲量下降1；原失败报告不改写。后续状态比较显式允许SD小写入下降0或1 MiB，其他字段及raw字节必须完全一致；只读允许变化0。没有NOR写入、录音、重启、ROM进入、helper运行或CPU/DMA模式切换。

baseline独立HCI核对：17条Boyi内容通知总计3852B，逐字节等于保存的partial；长度为`[244,244,24] + 13×244 + [168]`。**不能假定八组固定512B帧**。实际发送函数负返回时重新按剩余长度取最多512B，重试可改变分组边界；它与现象兼容，尚无现场返回值证明具体根因。

接续关注两个可区分的问题：小文件通道能否读取实际logsrv堆上下文，以及是否存在可验证的稳定日志快照合同。直接分八次读可变ring不保证原子性或新鲜度，不据此推进整片NOR；[CPU/DMA切换审计](archive/log-ring-freeze-boundary-2026-10-14.md)存在无超时等待及恢复失败忽略，也不作为冻结锁。

## logsrv独立上下文实测

[原始字节、收据与复验](archive/logsrv-context-live-2026-10-14.md)：新增三处代码守卫96B匹配；随后global4B得到`P=180111fc`，独立P/32B采样完整通过。flags=3、type/newtype=0、rd=wr=204、slot4长度139、drop=0。两次完整Actions/下载/结束状态验收；指针试验空闲量59597→59596MiB，其余不变。此次新增五个SD文件；截至该采样累计十七个。

这是pre-STOP历史元数据，尚未读槽正文；两次采样非原子，RAM边界检查不证明期间指针持续有效或当前堆归属。它为一次固定已知mdb输出→指定槽→512B新文件试验提供依据，仍不证明该路径可用或可推广到NOR。

## 已知mdb16→slot→新SD512，一次真机通过

[完整验收与公开收据](archive/logsrv-slot-live-2026-10-14.md)。先增加两段布局/复制代码守卫80B，再独立重采global4/context32；指针、stream、flags/type及完整rd/wr204保持预期。然后唯一一次试验执行：PREPARE、START、global4新随机路径dump、固定`dbg mdb 1000ab40 10`、context32 dump、slot4/512 dump、STOP。

实际7次ATT写及7ACK、F1、空pending均通过；三个文件分别完整下载4/32/512B。metadata槽4长度431；正文限定`slot[8:8+431]`，唯一完整本次done标记在body`[138,191)`，随后完整mdb行在`[195,274)`，含16B、ASCII和CRLF全部匹配既有独立代码oracle。原始slot512私有保存，公开仅安全标记与已知代码行，不发布未知旧尾部。

后置状态FW010004/NOTE/idle/charging，与开始相同，只有SD文件写入后的整数空闲量59596→59595MiB；本轮再保留七个非音频SD文件，截至本次累计二十四个。无重试、换槽、GPIO/MMIO读取、NOR producer/写入、模式切换、重启或ROM进入。

这证明一次本次标记关联的已知短读输出可经指定槽→新SD文件完整取回；不是原子快照、当前堆归属、采样时仍partial或任意512B读取可靠性的证明。下一项可据实际MDW宽度/输出合同选择单个对齐GPIO控制寄存器，独立验收；完整NOR与恢复仍未解决。

## GPIO28 CTRL：首次运行寄存器读回

[原件、适用边界与复验](archive/gpio28-word-live-2026-10-14.md)。两段现场守卫验证mdw入口width4和真正LDR32；新global/context采样counter206，选槽6，未沿用历史204。首次连接仅到服务发现即ERR110，无ATT写或Actions；第二次调用因路径日期输错在离线校验失败。两份失败报告保留。新独立连接首次实际发送固定`dbg mdw 40068074 1`，整体通过，无重复GPIO读取。

实际读值`0x00001805`，完整55B行（含ASCII/CRLF）在本次随机done标记后，均落在槽6有效前缀L406内。7写/7ACK/F1/空pending、4/32/512B下载及后置状态全部通过；before/after完整一致，free59595MiB。新增七份SD测试文件（两守卫、两preflight、三trial），累计31份；无寄存器/NOR写、录音、重启或ROM进入。

LARK定义解释为MFP5/UART0、SMIT位0、普通上拉、驱动等级1；早期表4125是SMIT1、强上拉、等级4。实际setter仅覆盖mask7f3f，不能把早期表当当前寄存器值，更不能据位配置宣布物理UART可用。GPIO29及SD引脚当前值仍未实测；完整NOR与恢复仍未解决。

## slot0两字：实际映射起点与CRC属性

[合并收据与复验](archive/map0-entry-live-2026-10-14.md)：两个固定单word目标分别新采pointer/context。`40010300=1000000f`（counter208/slot0），`40010304=00024000`（counter210/slot2）；各自7写/7ACK/F1、4/32/512B下载、nonce→55B行及后置状态完整通过。第二目标首份context32虽收全但后置info ENOSYS，原报告保持失败；使用另一份新采样context-b作parent，不重用失败采样或派生改判。

两个时点分别支持CPU地址高位10000000、初始化低f编码、物理offset候选24000及bit31=0；不称原子entry、不推窗口大小，CRC属性不等于分区加密标志。actual recovery是caller先给1000000f、helper再OR1；boot另一实现才ORf。仅静态已验证普通LDR读取，不改变映射或探测新alias/镜像之外地址。

新增十一份SD文件（含失败context），累计42；未写MMIO/NOR、录音、重启或ROM进入。该结果不解除整片原始NOR出口缺口；已枚举命令没有SD文件分片/截断接口，同名短写不缩文件。

## 既有RAM4096：7.5ms/CE1策略首个完整结果

[完整参数、收据与复验](archive/sd-interval-live-2026-10-14.md)：只读原固定RAM文件，无Actions或SD写。原认证入口因stdin EOF在设备I/O前失败；保留原报告。新目录b首个实际硬件trial从45ms连接基线发送一次更新，HCI确认interval6=7.5ms、latency0、原timeout500、CE hints1/1；同handle参数在整个下载期间有效。

完整4096B SHA256`35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b`与独立系统初始化切片逐字节一致。前后FW010004/NOTE/idle/charging及free59593MiB全部相同，最终报告ok=true；115条HCI记录/8554B保留私有，监控55s退出。不是纯interval单变量实验，也不是历史15ms条件的受控对照；本次实际完整结果不改判过去失败。

没有新SD文件，累计仍42。下一阶段仅新context28→ring基线4096→已知boot0，分别验收，不自动扩展未知页/批量任务。整片NOR、可恢复烧写和自建固件运行仍未完成。

## 新ring基线与boot0：首次新策略原始NOR闭环

[原件与复验](archive/sd-nor-interval-live-2026-10-14.md)：fresh context28为rd=wr1284、used0、capacity4096、buffer1803ee09、init1/panic0。首次连接在Actions服务发现超时110，未发ATT写/SD写，结束状态一致；失败报告保留，另一次独立context-b完整通过。

新baseline含唯一完整当次dump echo且无旧NOR行；新boot仅一次`dbg fread spi_flash 0`及新ring dump。二者均完整下载4096B，Actions分别4/5ACK+F1，HCI确认7.5ms/CE1策略覆盖整个下载。boot32连续行解析出的原始512B与旧独立oracle全字节一致，SHA72952…7ec；前后free59593及其他完整状态一致。

新增三份SD测试文件，累计45；未写NOR/MMIO、进入ROM、复位或执行新代码。下一有界目标是已知非零offset4200双读；每次必须新producer/新文件/新连接，而非同一文件读两次。

## 非零offset4200：独立双读与真实监控早收尾

`artifacts/nor-sd-offset4200-20261014/{first,second}`各自新建SD文件、重新执行一次`dbg fread spi_flash 0x4200`、下载完整ring4096。两份原始512B分别匹配已固定完整recovery-raw[512:1024]，彼此全字节一致；SHA256`51327e9d7a7d8d4c3538c83688753b5f99735b85e981756effb63efd1dc33713`。每份5ACK/F1、nonce/status/连续32行、完整HCI参数门槛及前后状态通过；纯离线verify_pair复验完整父链/Actions/HCI/字节并检查不同文件和有序独立采集。

真实btmon两次均收到owned-sudo SIGINT并正常exit0，完整capture112/113记录；解析及hash通过后才接受早收尾。不是退出码即成功。前后free59593及其他状态一致，新增两份文件，累计47；没有NOR写、ROM进入或固件执行。此结果验证已知非零读取和重复性，不计作新增recovery覆盖。boot1的offset2000首512早有全FF双覆盖；下一真正缺失扇区为2200，仍需独立双读。
