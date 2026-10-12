# 录音下载路径与DSP提取边界

2026-10-12，FW010004离线分析。[字节证据](evidence/recording-download-path-2026-10-12.json)。没有发送新下载请求、异常路径或设备命令。

**Boyi GET_FILE_DATA正常路径将名字包装成`/SD:/RECORDER/Call-<name>.mp3`，失败后尝试`Note-<name>.mp3`。现有录音下载不是直接按绝对路径打开文件的接口，不能直接用于`/NOR:K/aeRECORD.dsp`导出。** 这是实际构造行为的结论，不是关于所有服务都无资源读取能力的断言。

## 命令到线程

[已确认dispatcher](vendor-dispatch-followup.md)的0b命令传payload pointer/length到`1009edd6`。完整handler `1009edd6..1009ee0e`：将length−4作为名字长度，复制名字并补NUL，尾部4 B反转字节序后作为offset，调用`1000b998(name,offset)`。

因此本机handler没有在这个函数中把名字长度固定为14；14 B是官方App/当前CLI的正常协议约定，不能把客户端限制误写为固件验证。异常长度、分配失败和边界行为不在本轮测试范围。

完整scheduler `1000b998..1000ba1a`将名字复制到context+49，将offset存context+14c；context+18没有线程时创建entry=`1000b571`、stack大小800（十六进制）的工作线程。此处还有未展开的状态helper；不将线程创建等同成功文件读取。

## 文件构造与读取

worker片段`1000b570..1000b688`以格式`%s/%s%s.mp3`、目录`/SD:/RECORDER`、prefix `Call-`和context+49名字组装路径，调用`1002e978`打开；失败后换prefix `Note-`再打开。两次均传flag3；固定SDK [FS_O_RDWR](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/fs/fs.h#L139-L143)对应读写模式。后续所审计的数据循环执行读取，不由open模式推断它实际修改了文件。

成功后`1000b688..1000b6c6`先seek末尾、tell取得长度，将长度按大端放入0b开始回复；然后seek到context+14c请求offset。循环在`1000b72e`请求最多`0x4ef2`（20210）B，负值走错误、0走结束、正值传`10051980`。传输helper及线程全部状态门未在本轮完整验证，不能由这些片段断言可靠重传或分包契约。

## 能排除和不能排除的部分

- 普通名字不是原样传给fs_open，传入`aeRECORD.dsp`会被增加录音目录、Call-/Note-前缀与`.mp3`后缀。
- 现有CLI继续只接受列出的录音名；无需为了DSP提取放宽路径校验。没有实现或试探路径穿越、异常长度或其他控制流。
- 未发现可从此正常接口直接指定`/NOR:K/`的参数；不把这个有界结论扩大到其他命令、调试服务或官方升级机制。
- DSP取得仍需独立资源读取通路。已知shell SDFS/NOR输出使用printk，现有BLE正文通道不覆盖它，见[读取通路](readback-routes.md)与[实际printk后端](printk-backend-readback.md)。

本轮减少了一条无效的直接提取假设，没有新增整片备份、DSP导出或刷写能力。
