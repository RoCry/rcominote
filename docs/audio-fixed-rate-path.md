# ABTP测试中的固定16 kHz录音构造路径

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无设备I/O。[原始窗口](evidence/audio-fixed-rate-analysis-2026-10-12.json)保留两个完整函数及另一caller的明确局部片段。

**已找到ABTP麦克风上传测试中的固定16 kHz、ADC、16-bit、输入key4000构造路径。** 后续归属证据见末节；普通录音配置与设备当前运行状态仍未知。

## 从入口到ADC

1. 完整入口`100031ec..100031fe`比较r0与1；不等则返回。相等时，将原r1复制到r2、加载callback形状literal到r0、令r1=`3e80=16000`，通过`100031f8 B.W 10003430`尾调用包装函数。
2. 完整包装函数`10003430..10003560`保存传入r1，成功分配相关状态和buffer后，在`100034ea`执行`UDIV r2,r5,1000`；随后r0=5、r1=r2、r3=1，stack另有1和buffer/context形状pointer，调用`10057290`。
3. 已核对的[constructor与adapter](audio-parameter-adapter.md)将constructor r1作为sample rate传入。因此这条入口固定16000/1000=16，而非从参考SDK默认16 kHz猜测。
4. stream type=5由实际policy得到channel8、ADC key4000；adapter固定width0，与SDK16-bit enum一致。板级key4000返回0003/0000，但物理通道含义仍未解。

wrapper有多个分配失败返回，以上描述成功构造路径；本轮不据此声称分配必成功或音频采样实际发生。入口并未执行，callback/异步buffer生命周期亦未仿真。

## 另一个调用点保持动态

此前找到的`100622ce BL 10057290`前：r1取某对象+19 byte，r2取+1a byte，r3来自另对象+9a byte。相邻控制流片段还从+3加载stream type。该大函数没有完整展开，状态字段也未读取；不能把第一条路径的16000套到这个调用者。

## 调用搜索边界与方法修正

上一轮仅搜索直接BL命中两个constructor候选。继续追踪wrapper时，BL未命中；扩大为Thumb宽分支候选后找到真正的`B.W`尾调用。这说明BL目录不覆盖tail call，未命中不能当作函数不可达。

对入口地址的固定Thumb pointer字节搜索未命中，也不证明入口不会被调用：直接branch、计算地址、表偏移、ROM/其他镜像均可能绕开该搜索。下一步需核对入口的branch引用及用户模式关联；在此之前标注为“固定配置代码路径”，而非“已验证的当前录音设置”。

## 触发来源已收敛：ABTP麦克风上传测试

后续[parser与循环字节证据](evidence/audio-abtp-attribution-2026-10-12.json)将上述固定路径归属到ABTP，而非正常录音文件配置：

- 完整parser `10003274..10003338`读取packet+2 u16命令；`7161`进入`1000330c`分支，调用接收helper，返回0后从临时buffer读取两个word，`1000331a BL 100031ec`。
- parser allocator的标签literal指向实际字符串`abtp_cmd_parse`；外层完整循环`10003340..1000341a`日志字符串含`ABTP:%x`，识别连接形状命令7063后才设置本地flag，其他命令需该flag才进入parser。
- 固定SDK [abtp_inner.h](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/tool/spp_test/abtp_inner.h#L44-L53)将7161命名为AUDIO_UPLOAD_START；[abtp_entry.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/tool/spp_test/abtp_entry.c#L46-L59)的mic upload分支调用mic_data_start_capture、固定MICDATA_SAMPLE_RATE，与实际type1→16000的路径吻合。属于代码与标签共同归属，不是仅凭邻近字符串猜测。

**当前结论：固件含16 kHz麦克风上传测试路径；普通录音模式的采样率仍未知。** 本篇前文“触发来源未确认”是较早阶段；本节取代该范围描述，但ABTP实际transport是否可达、连接认证/权限、host工具格式及用户触发条件仍未验证。没有向设备发送ABTP命令。

实际parser可见比较值5441、7061、7161、7361、7761；其他值返回7。SDK头文件另列READ_MEMORY/READ_STORAGE常量，**不等于此parser实现对应处理**。这两个读取命令没有出现在该完整parser的分支中；不能据头文件将ABTP宣称为已发现的Flash备份通道。AT转发handler及接收helper尚未审计，也不在此次结论范围。
