# 固定16 kHz录音构造路径

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无设备I/O。[原始窗口](evidence/audio-fixed-rate-analysis-2026-10-12.json)保留两个完整函数及另一caller的明确局部片段。

**已找到一条固定16 kHz、ADC、16-bit、输入key4000的构造路径。** 尚未证明它对应哪个用户可见模式、何时触发，或设备当前正在执行该路径；不能说所有录音都固定这一配置。

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
