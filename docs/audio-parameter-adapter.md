# 录音参数适配层：固定16-bit与输入key策略

2026-10-12；完整实机FW010004映射镜像离线分析，无设备I/O。[字节证据](evidence/audio-adapter-analysis-2026-10-12.json)包含完整binding、adapter、两个policy函数；上层constructor仅保留明确标注的局部片段。

## Binding与参数适配

完整`1002ab5c..1002ab9c`加载实际`audio_in`字符串，调用已证实device binding函数，结果写全局`1800f728`；NULL返回−19，非NULL返回0。完整adapter `1002abb4..1002ac30`读取该全局，取API首slot间接调用上一轮的[实际open](audio-open-path.md)。adapter自己没有再次检查binding pointer为NULL；依赖外层初始化顺序。

以adapter输入pointer为P，输出临时ain_param为A：

| 输入/行为 | A字段offset与用途 |
|---|---|
| byte P+2 | A+0，sample rate |
| byte P+3 | u16 A+2，channel type；adapter只接受8 |
| 清零A前20 B | A+4 width固定0，SDK对应16-bit；非沿用上层width字段 |
| u16 P+4 | 临时ADC setting首u16，地址写A+8 |
| signed u16 P+a | 同一值复制到临时ADC setting+2/+4/+6/+8；增益形状，具体单位未定 |
| word P+14/P+18 | A+14/+18，callback/context形状 |
| word P+10 / u16 P+e | A+1c/+20，reload地址/长度形状 |

offset均十六进制。A位于stack+0c，ADC setting位于stack；只有channel=8时构造并调用API，其他值记录错误后返回NULL。因此这条adapter路径即使上游策略能产生I2S/SPDIF枚举，仍拒绝它们。

这进一步收窄上轮“open接受width 0或3”：**此adapter实际只传0**。不代表所有可能调用者都只能16-bit，也没有证明当前设备正在录音。

## 上层constructor片段

`10057380 BL 1002abb4`是全镜像按halfword边界扫描BL候选后人工核对的实际调用点。包含函数入口的片段`10057290..10057388`显示r0→stream-type状态、r1→采样率状态，后者再写入adapter P+2；未在此处固定采样率。

两个完整policy函数：

| 输入stream type（十进制） | `100ae284`产生ADC key | `100ae2ec`产生channel |
|---|---|---|
| 6 | 8000 | 8 |
| 22 | 2000 | 8 |
| 14 | 4000 | 10 |
| 15 | 4000 | 20 |
| 其他 | 4000 | 8 |

输出十六进制。constructor将channel写adapter P+3、key写P+4。key4000在实际板级映射表对应输出0003/0000，但输出字段的物理通道语义仍未审计；不能仅凭默认key判定模拟麦克风数量。

上层输入buffer分配和尺寸选择也存在条件分支，本轮只定位其传递链，不将局部路径推定为所有录音的固定buffer大小。constructor完整范围、实际录音调用者的stream type/sample rate仍待追踪。

## 范围与下一步

证据JSON列出constructor的直接BL候选，扫描覆盖当前完整映射镜像的halfword位置；不排除数据误命中、间接调用、ROM及其他分区代码。下一步逐个核对候选周围的参数构造，而非从SDK示例16 kHz直接推断CoMi实际设置。
