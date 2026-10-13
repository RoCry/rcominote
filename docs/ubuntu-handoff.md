# Ubuntu 接手：CoMi 真机研究

2026-10-13。仓库`~/w/_hw/rcominote`，分支`main`。保持原目标：实用CLI、实际硬件/固件/SDK理解、完整NOR备份、可靠恢复、自写固件运行；后三项仍未完成。先读本页，再按需查[当前路线](research-routes.md)和[平台地图](device-platform-map.md)，不要重做历史泛搜。

## 接手范围与现场

- Ubuntu本地负责下一轮Linux BLE/HCI验证；接手前确认Mac会话没有同时连接CoMi。不要让两个agent竞争硬件。
- 设备序列号`C261CF0430`、public MAC `50:C0:F0:AE:7C:0E`、广告名`CoMi Note 2F01`、既有FW010004；始终按广告序列号选中，不凭名称选首个设备。
- 用户最初说距离PC约3m，随后明确已将卡放在Linux主机旁边。最后一次应用状态来自前轮Mac：NOTE/idle；本轮仅连接、服务发现及MTU通信，没有录音/模式/配置/固件写入。下次需重新观察状态，不把旧状态当当前证明。
- Linux：BlueZ5.72，kernel6.14.0-36-generic，hci0 Intel适配器。`btmon`、`gatttool`可用；`rg`未安装，Ubuntu可用`grep`。uv管理的Python缺`socket.AF_BLUETOOTH`，新实验用已核对Linux ABI的ctypes bind/connect。
- 本轮所有`btmon`均有timeout，已结束；没有后台录音或待收尾的连接。未重启服务、改全局ControllerMode、配对、删除缓存或升级系统软件。

## 为什么旧Linux路径失败

[HCI/源码摘要](evidence/linux-le-hci-2026-10-13.json)。完整抓包含周边设备，留在Ubuntu和Mac忽略目录`artifacts/log-hci-2026-10-13/`，不要整包公开。

1. 普通`uv run comi info`经Bleak→BlueZ Device1.Connect，**实际发BR/EDR Create Connection 0x0405**，随后Page Timeout0x04。CoMi广告flags02未声明BR/EDR不支持；BlueZ5.72将两个bearer时间同时更新，平局优先BR/EDR。不是已经证明的CLI线协议超时。
2. 5.72 `bluetoothctl connect`没有`le`参数；`ConnectProfile`也不能强制LE。实验性Adapter1.ConnectDevice未在现有daemon暴露。不为本任务重启全机蓝牙或擅改配置。
3. `gatttool -t public --primary`明确发LE 0x2043。原位置RSSI−88，初步连接后remote-features/断连reason0x3e，未到ATT。靠近后RSSI−76，收到GAP/GATT/Battery、Actions、F5F0、E5E0服务回复。
4. 靠近试验中，设备主动发MTU请求`02f700`；gatttool回复`0102000006`（不支持），设备又回复对ErrorResponse的ErrorResponse。工具报Unlikely Error，**却退出0**。因此不能用exit0验收。`-m247`在该版LE路径不解决此问题，交互主动MTU也不等于支持对端请求。

固定BlueZ源码commit `770ad5614e7e8074133e6f563495ce4822f63fe4`；地址选择[adapter.c](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/src/adapter.c#L7272)、[device.c](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/src/device.c#L2480)，[GATT server MTU oracle](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/src/shared/gatt-server.c#L1502)。

## 修正版真机结果与下一步

`860a73a`的CID4 bind修正已于03:28 UTC真机复验：LE连接、双方MTU247、完整服务发现、Actions特征/CCCD均成功。随后`help`仍缺第二个512 B帧的首244 B；**HCI已经缺片**，不再怀疑Python拼帧丢掉这一片。[逐字节收据](evidence/linux-log-hci-loss-2026-10-13.json)。

- HCI #552–554等于独立旧成功帧1；#555–556等于帧2的`[244:488]`、`[488:512]`。没有`[0:244]`。
- HCI共11个日志通知；socket记录9个，与HCI前9个逐字节相同；解码器只消费7个。严格解析失败后STOP清理仍读同一个坏stream，再失败并关闭socket。
- HCI仍有完整帧3、help ACK、STOP ACK、F1。报告`ack_count=2/end_received=false`不是设备没发ACK/END的证明。原始捕获在两机`artifacts/linux-att-bind-check/`，所有进程已结束，无录音/配置/固件写入。
- 没有空口抓包，不能断言设备固件一定是根因；尚不能区分设备发送/控制器、无线链路、主机控制器/驱动。Mac与Linux同样缺片削弱了单一宿主上层错误的解释。

离线复验（无需硬件）：

```sh
uv run tools/verify_linux_log_capture.py artifacts/linux-att-bind-check
```

下一轮不要原样重跑`help`或重查BlueZ连接。若继续独立定位：失败后原始ATT收集现保留0.5 s窗口，本次全部ACK/F1已收；这不是任意链路的结束保证。保留原始失败判定，禁止重同步/补造。只有已具备BLE空口嗅探硬件时，再同步一次空口与HCI，判断缺片是否真正发送/确认；不假定现场已有嗅探器。

短输出替代已做一次，**未通过，不原样重试**：`f873545`的`linux_log --short-read`读取固定`1000ab40`16 B，逐条`kernel version`填充、上限8次；第6次时日志到达，但首512 B帧只有244+244 B，随后出现完整55 B新帧，缺24 B尾部。HCI与socket全部14通知逐字节一致，含最后ACK/F1。[完整实验收据](evidence/linux-short-read-2026-10-13.json)。目标行在原始不完整帧中可见，严格校验拒绝成功；没有去读GPIO/ADC、启动录音或扩展地址。

此方法复用旧`nor_batch.py`，依据是504 B缓冲满才推进wr；8次是历史经验上限，非理论保证。结果表明避开`help`仍不足以恢复可靠读取，不能把它升级为正式CLI能力。下一步须有新变量/证据（如同步空口抓包或实际设备发送链定位），否则回到板级/匹配M4 BSP/恢复资料主线。需要HCI时继续用有界`sudo timeout --signal=INT 60s btmon -i 0 -w NEW.btsnoop`，不常驻，不覆盖旧证据。

## 不能丢的其他结论

- [日志缺片复验](log-buffer-wrap.md)：Mac失败捕获相对独立旧成功帧缺首244 B，后268 B完全匹配；不是解析器误切，也不能只用封帧前ring丢文本解释。Linux已缩小到HCI观察点之前，仍不能把SDK潜在bug直接当本机根因。
- [NOTE/CALL](note-call-audio-2026-10-13.md)：模式/文件枚举已真机纠正；选定BLE START不强制同模式；132项增益表与LARK SDK匹配，请求36.5/40.5 dB，ADC字段不同。运行GPIO/ADC和物理拾音器切换仍未读回，用户说听起来相近。
- 完整系统、boot0、recovery、DSP及部分配置已取得；**不是完整4MiB原始NOR备份**。无可靠原厂恢复、ROM独立退出或自写固件上机证明。不要为了进度盲进ROM、执行helper或刷写。
- USB原配线数据接线未证，普通模式未枚举；Wi-Fi没有本机链路证据。旧NOR逐扇区日志路线已退役，未先证明可靠性/吞吐改善就不重开。

改动后`just check`、`uv build`，按真实结果更新现有报告再commit/push。Ubuntu接手后它是本阶段代码/证据的权威工作树；Mac只fast-forward同步，避免两边修改同一功能。
