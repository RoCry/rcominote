# 录音编码器：实际选择MP3 DSP路径

2026-10-12；C261CF0430 / FW010004。完整校验system映射镜像离线分析，无设备I/O。[字节证据](evidence/recorder-codec-dispatch-2026-10-12.json)包含完整分派/selector、14条codec记录及明确标注的DSP初始化片段。

**此前format1与`opus_ringbuf`名称的歧义已缩小：实际codec表为format1编码方向选择MP3标识、硬件加速及`aeRECORD.dsp`。** 这是固件选择路径的证据；未执行DSP、验证加载成功或验收输出帧。

## 实际分派

[媒体捕获参数](recorder-media-config.md)设置format1、stream10。capture初始化把format放到state+9a，在`100621b4`调用`100b098c`。

完整分派`100b098c..100b09bc`以state+9a和方向0调用`100595ac`；非零尾调用`1006294c`，零尾调用`100b0e18`。前者是本轮追踪的DSP路径。

三个完整selector使用同一表`100bd4bc`，扫描14条、每条20 B，以byte+0/+1匹配format/direction：

| Selector | 匹配时返回 | 未匹配 |
|---|---|---|
| 100595ac | byte+2：硬件加速标志 | 0 |
| 100595dc | word+0c：DSP库名pointer | NULL |
| 1005960c | word+10：DSP效果库pointer | NULL |

选中第10条（从0计数），地址`100bd584`：

| 字段 | 实际值 |
|---|---|
| format / direction / hardware | 1 / 0 / 1 |
| overlay word+4 | 6533706d，内存字节`mp3e` |
| ops word+8 | NULL |
| library word+0c | 100d1ff9 → `aeRECORD.dsp` |
| effect word+10 | NULL |

解码方向还有format1/direction1记录，overlay为`mp3d`。编码记录与固定SDK的[MP3硬件编码配置](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/media/codec_config.c#L270-L285)一致；[overlay定义](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/section_overlay.h#L35)也明确将6533706d标为LIBAEMP3。结论不再只依赖公开SDK的format枚举。

## DSP参数准备

`1006294c`入口从param+3取得stream，调用`100ae2b2`；完整policy只对stream7/12返回1，对当前stream10返回0，因此进入`100629fe`分支。

该分支清零stack+18/+1c，以format1、direction0分别调用library/effect selector，把`aeRECORD.dsp`指针放stack+18，effect保持NULL；stack+10/+14为1/3f。随后在`10062a28`将stack+10传给`1002b978`。后续session创建、资源查找、DSP启动尚未完整审计。

## 对自写固件的意义

- `opus_ringbuf`/`opus_stream_init`是[输出stream](recorder-stream-path.md)的名字，不能据此判断该录音配置使用Opus。
- 保留当前MP3路径需要核对DSP库内容、加载协议和资源位置；仅移植ARM侧ADC与stream不足以证明录音编码可用。
- 现有system映射导出没有证明覆盖对应DSP资源，仍不构成完整备份。暂不能据此设计可恢复的刷写方案。
- 下一步优先追`1002b978`及库名解析，建立DSP文件→资源分区的证据；文件名本身不证明文件存在、可导出或可复用。实际录音模式和输出帧验证另行保留。
