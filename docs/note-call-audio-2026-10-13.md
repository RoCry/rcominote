# NOTE/CALL：实际模式、GPIO 与 ADC 参数

2026-10-13；固定完整原厂 system 离线分析，加独立真机模式/短录音验证。**屏幕 NOTE 对应原始模式1，CALL 对应2；CLI 已据此纠正旧 App 的错误标签。** 实际代码选择 GPIOB18 相反电平，并在录音启动时采用不同 ADC 输入增益。物理麦克风接线与实际电平/增益效果仍需独立验证。

## 真机结果与 CLI 修正

[独立现场证据](evidence/note-call-live-2026-10-13.json)：用户分别确认屏幕 NOTE、CALL；随后 GET_INFO 的模式 byte 分别为1、2，切到 CALL 的状态事件也为2。旧 CLI 将1显示为call、2显示为memo，现已修复为note/call；未知模式值明确报错。实验最初 raw01 的屏幕未独立观察，不能把旧标签当初始 CALL，也不能据此证明第一次按钮动作改变了模式。

| 用户确认模式 | info/event 原始模式 | START/STOP 文件kind | 完整导出 | ffprobe |
|---|---|---|---|---|
| NOTE | info1；本段无独立切换event | 1 / 1 | 24,228 B，实时/完整下载逐字节一致 | MP3、16 kHz、mono、32 kbps；6.057 s |
| CALL | info2、event2 | 0 / 0 | 24,374 B，实时/完整下载逐字节一致 | MP3、16 kHz、mono、32 kbps；6.0935 s |

两段均由 CLI 启动并停止，停止读回idle。修复后的 CLI 已再次在 CALL 真机读回call。录音内容属于未控制的环境声，留在忽略目录 `artifacts/note-call-2026-10-13/`；公开证据只留字节摘要、协议帧与格式。不能用这两段比较拾音效果，也不能将短文件下载速度当持续吞吐。两种模式的格式相同不证明麦克风或 DSP 相同。

实验后文件列表由8条变10条，原8条元数据不变，新增恰为两段自建样本；保留样本，未删除文件。原录音内容未重新下载，不能把列表核对写成原文件字节校验。设备停在用户确认的 CALL，等待下一轮手机播放对照；未声称已恢复 NOTE。

## 手机扬声器外放：一分钟 CALL 基线

[2026-10-13现场证据](evidence/note-call-phone-2026-10-13.json)。用户确认：录音卡磁吸手机背面、拔充电线、CALL；手机扬声器外放约4分钟循环视频，音量约30%。采集前读回CALL、idle、未充电、降噪9。CLI录制60s并停止，停止读回idle。

- 完整文件240,522 B；实时通知拼接与完整下载逐字节一致，SHA-256 `a20cccdc3934e00ec1afa832a1c0eebc867191ba8930b5204a4f0630b7815414`。
- ffprobe：60.1305s、MP3、16 kHz、mono、32 kbps；ffmpeg完整解码exit0。
- ffmpeg `astats=metadata=0:reset=0` 解码总体峰值−3.179423 dBFS、RMS−25.205896 dBFS、962496样本。这些是音频电平，不是声压级、可懂度或麦克风灵敏度。
- 完整下载6.9902s，34,408 B/s（约33.6 KiB/s）。一分钟文件可在约7秒导出；不外推长录音持续速度或无丢包保证。

视频播放相位未控制，本段没有同步声源参考，未作试听判断。扬声器同时向空气发声，不能由这段确定接触拾音器/骨传导路由。后续听筒样本见下节；视频与电话的内容及输出音量不同，不直接比较两者的电平。

本地私有音频/日志在 `artifacts/note-call-phone-2026-10-13/`，只提交数值和协议证据。复验命令（`FILE`为本次完整下载的MP3）：`ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bit_rate:format=duration,size -of json FILE`；`ffmpeg -hide_banner -nostdin -i FILE -af astats=metadata=0:reset=0 -f null -`。实时文件与完整下载另做字节比较。

## 电话听筒：CALL / NOTE 与一次断连恢复

同一份[现场证据](evidence/note-call-phone-2026-10-13.json)的`receiver_call`、`receiver_note`。用户先后确认“听筒语音已播放”“note 听筒已播放”；两次采集前分别读回CALL/NOTE、idle、未充电、降噪9。要求保持贴附和通话音量不变；通话音量档位、是否重播同一提示音、整个窗口是否持续播放未独立确认。此前视频30%音量不能套到通话。

| 样本 | 完整文件 / 时长 | 解码总体 RMS / 峰值 dBFS | 实时及停止结果 |
|---|---|---|---|
| 听筒 CALL | 80,246 B / 20.0615s | −27.140516 / −3.980331 | 实时与完整下载逐字节一致；正常STOP后idle |
| 听筒 NOTE | 91,764 B / 22.941s | −25.431554 / −3.681271 | 实时采集断连失败；新连接STOP后idle；仅完整离线文件成功 |

两份均MP3/16 kHz/mono/32 kbps，ffmpeg完整解码exit0。有非零音频信号不等于已证明提示音可懂度；没有同步源参考，不能由RMS差判断模式灵敏度、降噪优劣或物理麦克风路由。NOTE略长来自补救停止时序，不是码率/模式效果。用户试听反馈见下，不为凑重复样本再次录制。

后续用户试听反馈：**“感觉两个都几乎一样了”**。记录为本条件下未感到明显差异，非盲测/同步片段的等效性证明。模式状态和文件分类已确认切换，但实际GPIO电平、拾音器归属及声学切换效果尚未确认；不能将“模式编号正确”扩大成“麦克风切换正常”。

针对此疑问，[补充静态证据](evidence/note-call-runtime-static-2026-10-13.json)闭合了选定的异步UI桥：BLE opcode06→`1000abf4`→view37 handler `100142a4`→layout `10014314`→`1000d2d4`向launcher发送typeCD/cmd0→`100093b8`→`1000d9f0`→producer `1000d6a4`。这条启动路径未直接覆盖模式或调用模式GPIO helper；producer仍按当前模式选择gain。另一入口`1000dca8→1000dd2e`按参数选择mode1/2，也不是固定模式。常规START依赖此前手动切换留下的GPIO状态。已审路径不支持“CLI把两模式强制成同一路”的解释；这是静态消息路由，不是现场执行trace，未递归审完所有通用helper或后台副作用。

**真实失败序列**：NOTE采集`realtime --record --duration 20`退出1，错误为断连且同连接清理失败；新连接GET_INFO明确仍为recording；另一次`record stop`返回文件名、长度和idle，随后该文件完整下载、长度/hash核对、解码成功。断连发生的具体阶段和原因未捕获；不能归因于NOTE、听筒或手机干扰。失败没有发布成功的实时文件，也没有把离线补救写成实时一致。

这验证了既有CLI警告的实际意义：连接丢失不代表设备停止录音。此次靠新连接显式停止完成恢复；没有新增自动重连或停止他人录音的规则。测试结束保持NOTE待机。

### 收尾发现：一条旧测试录音缺项，尚未归因

此前列表10条，加本轮三段应为13条；两次新连接均返回12条。三段新增均存在，保留的旧9条元数据不变；缺项是此前自动创建的NOTE测试`20261012222510`，20,204 B。用户明确未删除/清理，本轮未发送删除命令。该旧样本最初`realtime-probe/report.json`已记录一次下载超时，不能把问题开始时间归到本轮。

仅作两次已知名称的只读导出：均收到20,204 B声明，却在19,960 B之后收到结束，CLI正确拒绝完整性验收。第二次原始交付另存`.partial.bin`；它与当时20,204 B实时样本相比，可表示为删去`[756,1000)`这244 B，其余逐字节相同。这个字节关系不证明缺失发生在存储、固件发送或BLE通知哪一层。

固定system的完整列表handler `1000b838..1000b97c`无12条/固定数量计数或已同步标志过滤；逐项readdir至空名称，筛普通文件、MP3类后缀及Note-/Call-名称格式。未展开底层文件系统/通知送达，不能排除那些层的问题。结论停在**可按名寻址、列表缺项、导出不完整**，不宣称删除或原文件完好。保留失败/部分数据及字节比对，未写入修复、未重建索引、未扩大重试；后续客户端可靠性任务可用此实际失败作为oracle。

以下均为**离线静态证据**；未读物理 GPIO 电平、未测增益效果、未执行新固件。

[原始字节与完整/局部指令范围](evidence/note-call-static-2026-10-13.json)绑定[原厂 system](evidence/minimal-image-2026-10-13/original-system.bin.gz)：解压927632 B，SHA-256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。地址、offset、消息号采用十六进制；表内注明十进制的数值例外。使用 Capstone，代码、TBB 与池数据分开保存；未执行代码或递归展开 DSP。

## 模式字段与线协议，不能共用一套枚举

运行状态基址 `1800ba00`；`RECORD_MODE` 位于 **`+470 = 1800be70`，1 B**。启动 `1000d1d2..1000d1e8` 从属性读取后保存；`1000d294` literal 指向实际字符串 `RECORD_MODE`。

| 路径 | 实际组装 | 解释边界 |
|---|---|---|
| GET_DEVICE_INFO | `1000ab46` 读 `ctx+470`；`1000ab4e` 写 `sp+13`；`1000abb2` 以 `sp+4` 为 payload，发送 opcode05 | **payload[15十进制]是原始模式byte，没有归一化** |
| 状态事件0f | `1000acb2` 读同一字段，写 `sp+7`；`1000acf0` payload=`sp+4` | **payload[3]同样是原始模式**；邻近 USB 字段确有归一化，但不能套到模式 |
| START成功回复06 | `1000b15c..1000b18a` 比较文件名前5 B | `Note-`→payload[15十进制]=1；`Call-`→0 |
| STOP成功回复07 | `1000b1be..1000b1ec` 比较同样前缀 | `Note-`→payload[19十进制]=1；`Call-`→0 |

原始模式值与文件种类值不同。文件名构造函数 `1000d858` 提供独立命名依据：`ctx+470==1` 使用 literal `1000d918→Note-`；`==2` 使用 `1000d92c→Call-`。本轮开始时客户端将 info/event 的值1显示为 CALL，与这些实际代码冲突；上面的独立屏幕/回复对照已完成修正验收，客户端旧标签不能当 oracle。

## 两种模式的完整对照

NOTE/CALL 栏按实际文件名前缀命名，与上面的独立屏幕/回复对照一致；电平、增益仍只是静态调用意图。

| 项目 | raw模式1 / `Note-` | raw模式2 / `Call-` | 实际依据 |
|---|---|---|---|
| `1800be70` | 1 | 2 | 属性、模式切换与文件名构造 |
| GPIO选择helper参数 | 0 | 1 | 启动 `1000d1e2` / `1000d252`；切换 `1000eb9c..1000ec10` |
| GPIOB pin18请求值（pin十进制） | 高1 | 低0 | `1002de28..1002de5a`，绑定 `GPIOB` 后配置pin，再调用set包装器 |
| 录音输入gain原始有符号halfword | `016d` = 365十进制 | `0195` = 405十进制 | producer `1000d74e..1000d75e` / `1000d7d0` → `1000207c` |
| gain保存地址 | `180015e2` | 相同地址 | policy对象`180015d8`的`+0a` |
| stream type / ADC channel / key | `0a` / `08` / `4000` | 相同 | producer、policy与既有adapter路径 |
| 采样率/位宽/通道/编码 | 16 kHz、16-bit、单声道、MP3/32 kbps | 相同 | 参数固定word及[codec分派](recorder-codec-dispatch.md)；配置不是输出实测 |
| media param+3c | `DENOISE_IDX`当前值 | 同一个字段 | `1000d78c`读`ctx+0c`，不是模式byte |
| mode独有DSP镜像/算法 | 未建立 | 未建立 | 已审入口没有另选codec；不从相同MP3配置反推DSP内部处理相同 |

### 增益链与时序

`1000207c` 将增益写到 policy+0a，再将 policy 指针交给 `100571e8`，保存于 `180195b0`。录音 constructor `10057290` 对 stream10 调用 `100570cc`；其 TBB 进入 `10057100`，从 policy+0a **有符号读取**输入gain。`10057306` 存入对象+0e，随后 `10057336..38` 连同相邻字段搬到 adapter 参数；其中 P+0a 就是该gain。

[完整 adapter](audio-parameter-adapter.md) `1002abb4` 将 P+0a 复制到四个 ADC gain 字段；[既有 policy](audio-parameter-adapter.md)对 stream10 保持 channel8/key4000。这是同一 ADC 入口使用不同gain的证据，**不证明切换了哪个芯片内部ADC通道，更不证明安装四颗麦克风**。补充核对已建立增益单位和实际ADC字段，见下。

gain写入发生在 producer 创建录音链时。**仅待机切换模式，`180015e2`可能仍保留前次录音值**；应在对应模式录音已启动后观察，不能把待机旧值判为异常。两个已知producer caller `1000da9c`、`1000dd2e`都进入同一参数构造；后者所在 `1000dca8..1000dd4c` 先设置模式和GPIO，再创建文件/媒体。

### 已核实增益单位与硬件字段；尚无现场读回

[固定SDK的API合同](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/audio/audio_in.h#L292-L301)定义请求值为dB的10倍。实际系统`100bfd54`的132项、每项6 B增益表，与同一commit的[phy_lark ADC表](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/audio/phy_lark/phy_audio_adc.c#L706-L839)全部字段一致；实际选择器取首项gain≥请求，365/405均精确命中不同项。47段原始字节已逐项与固定system核对，SDK文件及表hash见补充静态证据。

| 配置 | NOTE | CALL |
|---|---|---|
| 请求输入增益 | 36.5 dB | 40.5 dB |
| 表index（十进制） | 44 | 52 |
| input_res / feedback_res / digital_gain | 1 / 13 / 4 | 2 / 14 / 3 |
| ADC ch0 digital：`4005c104 & 0000000f` | `4` | `3` |
| ADC ch0 analog：`4005c130 & 0000f003` | `0000d001` | `0000e002` |

实际key4000板级映射为`03,00,00,00`；匹配LARK驱动解释为ch0差分输入，其余禁用，并跳过单端输入的+60补偿。两模式不是请求不同却量化到同档；数字字段单独较小不代表总增益更低，需连同模拟字段解释。**4 dB是API请求差，不是最终录音响度实测差**；这些配置不识别外部拾音器、隔离程度或物理麦克风数量。不能仅据此解释听起来相似的原因。

固定地址实验工具在`src/rcominote/experiments/audio_state.py`，需显式`--record`：先校验本地镜像hash、设备身份和现场代码字节，之后才启动一段自有录音；读取mode/policy/gain及三个32位寄存器，并按文件名核对录音归属再停止。只允许固定读地址；不写RAM/MMIO。寄存器读依据是实际驱动的普通LDR/读改写，尚无独立芯片手册证明。**工具未通过真机验收，不是可用CLI能力。**

[现场失败与对照](evidence/note-call-runtime-attempt-2026-10-13.json)：首次在第一条代码guard的`mdb+help`阶段发生日志帧错误`20636c6561`，未发送录音START、未读运行RAM/MMIO。改用已有Actions-only诊断profile `commands`作一次对照，仍在504 B文本帧后收到非协议头`7973696361`。因此新工具同时订阅Boyi不是唯一解释；尚不能定位固件发送、BLE送达或其他层。两次均尝试日志STOP但未确认结束帧；随后独立GET_INFO成功，设备NOTE、idle、未充电，设置与容量字段不变。没有重启或刷写。

暂停现场读回，不丢弃错误字节、不自动重试、不将部分行当完整快照。原始对照通知已入库，离线回放验证严格拒绝；实验工具补充原始通知/残留和主错误保留。重开条件：已有明确的日志完整性修复或独立可靠读取通道；无需用户为了此失败反复切模式。若通道恢复，先验NOTE录音中ADC字段，成功后才安排CALL对照。

后续[传输定位](log-buffer-wrap.md#2026-10-13另一种失败完整帧的首个ble分片缺失)：与前日独立成功`help`逐字节对照，确认第二帧缺首244 B，后268 B完全相同；不能只归因于封帧前ring丢文本。SDK可见层未建立根因。Ubuntu虽扫到同机，两次连接超时，尚未形成独立主机诊断对照；Mac最终仍NOTE/idle。不改变上述现场读回边界。

### +3c 是降噪索引，不是麦模式

opcode17 setter `1000af98` 将输入byte写 `ctx+0c`，用实际 `DENOISE_IDX` 字符串保存属性；初始化默认9。GET_INFO将同一byte放到payload[39十进制]。producer再把它复制到media param+3c。因此不应再把+3c描述为尚未识别的NOTE/CALL参数。模式对照时须保留相同降噪设置，避免把降噪差异混入模式差异；具体DSP内部如何消费该参数在本轮边界之外。

## GPIO读回依据与限制

实际 `GPIOB` 设备描述符在 `100b9fc0`：config=`100bc1f0`，API=`100bc1c0`；config中base=`40068000`、group=1。模式helper配置pin18、flags=`200`；配置包装器 `100a4230` 清该pin的软件active-low位，随后 `100a424c` 据逻辑值选择驱动set/clear，故这里不是把低有效标志误当电平反转。

- API get_raw槽+4指向 `10030609`。实际 `10030618..22` 按 `base+230+group*4` 执行普通LDR并返回：**GPIOB输入采样word=`40068234`，目标bit18，mask=`00040000`**。该驱动路径没有清状态/应答写；固定SDK同源函数也将其命名为IDAT。[gpio_acts.c:41–63](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/gpio/gpio_acts.c#L41-L63)。
- 实际masked-output操作 `1003097c..8c` 使用 `base+200+group*4` 的读改写：输出锁存地址=`40068204`。独立set/clear路径使用另外的偏移；本报告不是向这些寄存器写入的建议。
- GPIO调用返回值未完整用来约束上层模式保存，字段/调用意图不保证引脚或外部器件已生效。输入读回也不能独自证明哪个拾音器受控；外部模拟开关、麦供电或其他用途需板级材料/声音实测区别。

## 足以支持的有界现场对照

保持USB、降噪等其他设置不变；由用户按说明书在待机切NOTE/CALL，分别保留显示模式、原始GET_INFO/event、一次短录音的START/STOP/列表种类与音频。若需定位电路差异，只比较已证明的模式byte、录音启动后的gain半字和GPIOB IDAT bit18；不写RAM、不探测未知寄存器、不扩大采集范围。最后恢复原模式并核对状态。

停止条件：标签、选定启动路由、增益单位及寄存器预期已解决；现场读取因日志完整性失败暂挂，不继续逐ADC或DSP callee展开。物理拾音器精确数量/接线、GPIO/ADC实际状态、DSP内部算法仍未知，等匹配资料或可靠通道再继续。这些结果增加音频BSP知识，不解除首次运行、整机恢复或完整NOR备份门槛。
