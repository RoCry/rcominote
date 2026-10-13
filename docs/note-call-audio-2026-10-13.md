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

视频播放相位未控制，本段没有同步声源参考、NOTE或听筒对照，未作试听判断。扬声器同时向空气发声，不能由这段确定接触拾音器/骨传导路由。下一步优先让电话自动语音走听筒，保持贴附、CALL、未充电；用户确认准备后再采集。若比较模式，尽量重复同一段提示音；不同内容不用于模式优劣判断。

本地私有音频/日志在 `artifacts/note-call-phone-2026-10-13/`，只提交数值和协议证据。复验命令（`FILE`为本次完整下载的MP3）：`ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bit_rate:format=duration,size -of json FILE`；`ffmpeg -hide_banner -nostdin -i FILE -af astats=metadata=0:reset=0 -f null -`。实时文件与完整下载另做字节比较。

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

[完整 adapter](audio-parameter-adapter.md) `1002abb4` 将 P+0a 复制到四个 ADC gain 字段；[既有 policy](audio-parameter-adapter.md)对 stream10 保持 channel8/key4000。这是同一 ADC 入口使用不同gain的证据，**不证明切换了哪个芯片内部ADC通道，更不证明安装四颗麦克风**。本轮不把365/405赋予dB单位。

gain写入发生在 producer 创建录音链时。**仅待机切换模式，`180015e2`可能仍保留前次录音值**；应在对应模式录音已启动后观察，不能把待机旧值判为异常。两个已知producer caller `1000da9c`、`1000dd2e`都进入同一参数构造；后者所在 `1000dca8..1000dd4c` 先设置模式和GPIO，再创建文件/媒体。

### +3c 是降噪索引，不是麦模式

opcode17 setter `1000af98` 将输入byte写 `ctx+0c`，用实际 `DENOISE_IDX` 字符串保存属性；初始化默认9。GET_INFO将同一byte放到payload[39十进制]。producer再把它复制到media param+3c。因此不应再把+3c描述为尚未识别的NOTE/CALL参数。模式对照时须保留相同降噪设置，避免把降噪差异混入模式差异；具体DSP内部如何消费该参数在本轮边界之外。

## GPIO读回依据与限制

实际 `GPIOB` 设备描述符在 `100b9fc0`：config=`100bc1f0`，API=`100bc1c0`；config中base=`40068000`、group=1。模式helper配置pin18、flags=`200`；配置包装器 `100a4230` 清该pin的软件active-low位，随后 `100a424c` 据逻辑值选择驱动set/clear，故这里不是把低有效标志误当电平反转。

- API get_raw槽+4指向 `10030609`。实际 `10030618..22` 按 `base+230+group*4` 执行普通LDR并返回：**GPIOB输入采样word=`40068234`，目标bit18，mask=`00040000`**。该驱动路径没有清状态/应答写；固定SDK同源函数也将其命名为IDAT。[gpio_acts.c:41–63](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/gpio/gpio_acts.c#L41-L63)。
- 实际masked-output操作 `1003097c..8c` 使用 `base+200+group*4` 的读改写：输出锁存地址=`40068204`。独立set/clear路径使用另外的偏移；本报告不是向这些寄存器写入的建议。
- GPIO调用返回值未完整用来约束上层模式保存，字段/调用意图不保证引脚或外部器件已生效。输入读回也不能独自证明哪个拾音器受控；外部模拟开关、麦供电或其他用途需板级材料/声音实测区别。

## 足以支持的有界现场对照

保持USB、降噪等其他设置不变；由用户按说明书在待机切NOTE/CALL，分别保留显示模式、原始GET_INFO/event、一次短录音的START/STOP/列表种类与音频。若需定位电路差异，只比较已证明的模式byte、录音启动后的gain半字和GPIOB IDAT bit18；不写RAM、不探测未知寄存器、不扩大采集范围。最后恢复原模式并核对状态。

停止条件：原始回复/显示/文件种类足以解决标签；静态与有界读回足以判断GPIO/gain是否随模式变化后，不继续逐ADC或DSP callee展开。物理拾音器精确数量/接线、gain单位、DSP内部算法仍未知，等匹配资料或明确听音问题再继续。这些结果增加音频BSP知识，不解除首次运行、整机恢复或完整NOR备份门槛。
