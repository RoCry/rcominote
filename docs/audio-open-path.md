# 实际audio_in open与板级输入映射

2026-10-12；C261CF0430 / FW010004。完整镜像校验后离线分析，无录音、设备I/O或MMIO访问。[证据JSON](evidence/audio-open-analysis-2026-10-12.json)保留两个完整函数及明确标注的ADC caller片段。

## Open真实支持范围

承接[初始化证据](init-audio-board-evidence.md)：audio_in API=`100bc590`的五项Thumb pointer为`10038695,10038549,10038005,10038881,100382bd`。首slot完整函数`10038694..1003882c`：

- NULL参数立即返回NULL。非NULL后获取设备data关联锁，处理固定session槽与busy状态。
- 参数+2读取u16通道位；后续仅低byte恰好8进入ADC分支，设备取audio_in data+1c（即init绑定的ADC_0）。
- 值10或20（十六进制）分支产生−6并走清理/NULL返回；不能因为通用头文件列出I2S/SPDIF，就宣称本机open支持这些输入。
- ADC分支只接受参数+4 byte为0或3，否则产生−22并清理。公开SDK enum对应16-bit/24-bit；这里首先保留实际数值约束。
- 通过ADC device API首slot调用`1003b811`，原始参数pointer原样传入。非零返回走错误清理；成功后取参数+8所指结构首u16保存到session+8。
- 输入的+14/+18保存callback/context形状字段；+1c/+20为reload地址/长度形状字段。地址非零但长度零会走错误分支；没有凭此宣称完整buffer校验。

固定SDK [ain_param_t](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/audio/audio_in.h#L361-L384)字段顺序、[channel enum](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/audio/audio_common.h#L163-L167)与实际访问支持上述解释。但尚未定位录音应用传入的具体sample_rate、width、input device或buffer，不能把支持范围说成当前录音参数。

## 板级映射表

ADC enable仅展开与映射相关的caller片段`1003b9d0..1003b9ec`：取ADC setting首u16到临时结构，调用`1002dcb8`。完整mapping helper `1002dcb8..1002dcf4`：NULL返回−22；扫描7项、stride6；匹配首u16后把后两个u16拷到输出+2/+4，返回0；未命中打印并返回−2。

实际表`100bfcf2..100bfd1c`：

| key | output+2 | output+4 |
|---|---|---|
| 8000 | 0002 | 0001 |
| 8001 | 0c03 | 0000 |
| 8002 | 0800 | 0400 |
| 4000 | 0003 | 0000 |
| 4001 | 0003 | 0000 |
| 2000 | 0002 | 0001 |
| 1000 | ffff | 0000 |

值均十六进制。SDK [board_audio_device_mapping](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_dev_watch_2cs_nor/board.c#L353-L386)具有相似查表语义，但当前源码是更多输出字段的结构；实际这里只有两个u16输出。因此本轮不赋予ch0/ch1或具体analog/DMIC含义，不直接照搬参考板映射。

这是固件支持的配置映射，不是物理麦克风清单。ADC enable包含其他调用和分支，本轮未完整审计，不宣称已还原上电、增益、采样时钟或输入选择算法。

## 下一步

优先定位实际录音调用者，取得其构造的sample rate、通道宽度、ADC setting key与reload buffer；再沿key到ADC寄存器配置确认输入模式。显示研究与这些音频事实仍不能替代原厂恢复入口、raw备份或首次固件加载验证。
