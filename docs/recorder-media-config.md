# 非ABTP媒体捕获：16 kHz单声道配置

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无录音或设备I/O。[字节证据](evidence/recorder-media-config-2026-10-12.json)包含完整参数生产函数与明确标注的caller/media-open片段。

**已找到独立于ABTP的实际媒体捕获参数生产者：输入/输出rate16、sample bits16、输入/输出channels1、bitrate32、format1。** 固定SDK布局/枚举支持解释为16 kHz、16-bit、单声道、32 kbps MP3配置；不是录音文件实测，也不覆盖所有模式。

## 实际参数组装

完整函数`1000d6a4..1000d7f4`先清零stack上的40 B（十六进制）参数结构，创建/打开stream，成功路径在`1000d7b2`调用`100591c0`。后者通过唯一`tws %d type %d dvfs %d`日志与公开media_player_open代码定位，并有实际参数pointer传入证据；本轮未完整展开其内部消息处理和编码器。

| 参数offset | 实际写入 | SDK对应解释 |
|---|---|---|
| +00 | byte02 | capture服务类型 |
| +03 | byte0a | stream type10；本机policy映射ADC/key4000 |
| +18..1b | word10101001 | format1、input rate16、output rate16、sample bits16 |
| +1c..1d | halfword0101 | 输入/输出各1 channel |
| +20..21 | halfword0020 | capture bitrate32 kbps |
| +24 | NULL | capture input stream未直接提供 |
| +28 | 实际stream pointer | capture output stream |
| +3c | 某状态对象+c byte | 额外运行时参数，不由本轮赋予语义 |

offset与打包word为十六进制，rate/bits/channels/bitrate解释为十进制。字段顺序依据[media_init_param_t](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/media/include/media_service.h#L420-L437)，格式值1依据[MP3_TYPE enum](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/media/include/media_type.h#L25-L31)。实际唯一word literal在1000d808，未从默认config猜测。

函数根据状态+460是否为1，把参数+a halfword设为58或0；附近日志为`denoise: %d, avr_mode: %d`。暂不直接把这个字段或数值翻译为去噪强度/阈值，避免仅凭日志附近字段猜含义。状态+470还影响另一helper参数，但不改变上述固定rate/channel word。

## 调用关联

- 实际`1000da9c`、`1000dd2e`直接调用参数生产者。
- 调用前通过格式`%s/%s`拼路径，传stack路径pointer；后者附近literal为`mic_start_ret: %d`。
- 参数生产者含`ble stream open failed`、`stream open failed (%s)`、`media_player_open failed`、`media_player_play failed`错误标签。这表明同时存在流和媒体启动上下文，但不能仅凭“ble”标签认定音频只发BLE，或仅凭路径格式认定已写SD。
- 该链与[ABTP固定16 kHz测试](audio-fixed-rate-path.md)的100031ec→10003430路径不同。两者恰好都出现16 kHz，必须保留独立证据。

## 能用于BSP的部分

此producer选择stream10；已确认policy将其映射为ADC channel8、key4000，adapter固定width0。key4000的板级映射值为0003/0000；仍需下层解释才能判定物理模拟/数字输入。单声道是配置的输出通道数，**不等于设备只有一颗麦克风**。

仍缺：调用者的用户可见模式归属、实际运行选路、录音文件头/编码参数、音频输入电气与采样测量、下层增益/输入选择。下一步应核对producer的stream目标或解析已有真实文件；不把静态配置写成已观测录音结果。

后续[实际codec分派](recorder-codec-dispatch.md)确认format1编码方向选中`mp3e`硬件记录与`aeRECORD.dsp`，支持MP3配置判断；[输出stream](recorder-stream-path.md)的`opus_ringbuf`标签不能据此改判Opus。静态选择不等于已验收DSP执行或输出文件。
