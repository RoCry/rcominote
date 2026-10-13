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

## 已备好的实验与唯一下一步

`src/rcominote/experiments/linux_att.py`：固定public LE/CID4，正确响应对端MTU，通知队列及原始ATT记录，超时/不匹配明确失败，关闭socket。`linux_log.py`：按序列号扫描，发现并验证Actions服务/特征/CCCD，然后仅执行PREPARE、START日志、help、dbg、STOP日志。**此START不是启动录音。** 无任意shell、RAM/NOR写入或刷机入口；不是正式CLI Linux支持已验收。

第一版真机在connect立即报EINVAL，未发送ATT。已按[BlueZ bind顺序](https://github.com/bluez/bluez/blob/770ad5614e7e8074133e6f563495ce4822f63fe4/btio/btio.c#L1955)修正：先bind本地ANY/public/CID4。Linux未bind时SEQPACKET仍是连接型channel，PSM0触发EINVAL；CID bind才转固定channel。**修正版有离线测试，尚未真机重试。下一步就是验证它。**

在两个本地终端分别执行；输出路径必须新建，已有时换后缀：

```sh
# 终端1：有限窗口HCI记录；不后台常驻
cd ~/w/_hw/rcominote
mkdir -p artifacts/linux-att-next
sudo timeout --signal=INT 60s btmon -i 0 \
  -w artifacts/linux-att-next/session.btsnoop \
  > artifacts/linux-att-next/session.btmon.txt 2>&1
```

```sh
# 终端2：直接使用Git中的修正版，不用旧的忽略目录源码副本
cd ~/w/_hw/rcominote
uv run -m rcominote.experiments.linux_log artifacts/linux-att-next/report.json
```

验收必须同时检查：

- HCI发LE连接，服务发现完整结束，Actions UUID/句柄/CCCD实际匹配。
- 设备若发`02f700`，主机回`03f700`；没有旧工具的错误响应循环。
- 实验JSON `ok=true`、5个Actions ACK、F1到达、pending为空，保留全部ATT收发与日志通知。
- 将HCI中Actions通知值与JSON通知逐字节比较。若HCI有完整数据而脚本没有，查主机；若HCI本身缺片，主机重同步不能恢复。
- 失败先按阶段和原始包定位；不重复同条件尝试，不把部分帧或补造字节当成功。诊断关闭与设备录音状态分别验收。

若读通，再用此可靠通道做当前NOTE录音中的固定GPIO/ADC只读快照；复用`audio_state.py`已审地址/归属保护，不直接把全部Bleak操作换成新后端。更长录音、CALL声学对照不在这轮。

## 不能丢的其他结论

- [日志缺片复验](log-buffer-wrap.md)：Mac失败捕获相对独立旧成功帧缺首244 B，后268 B完全匹配；不是解析器误切，也不能只用封帧前ring丢文本解释。丢失层尚未定位，不能把SDK潜在bug直接当本机根因。
- [NOTE/CALL](note-call-audio-2026-10-13.md)：模式/文件枚举已真机纠正；选定BLE START不强制同模式；132项增益表与LARK SDK匹配，请求36.5/40.5 dB，ADC字段不同。运行GPIO/ADC和物理拾音器切换仍未读回，用户说听起来相近。
- 完整系统、boot0、recovery、DSP及部分配置已取得；**不是完整4MiB原始NOR备份**。无可靠原厂恢复、ROM独立退出或自写固件上机证明。不要为了进度盲进ROM、执行helper或刷写。
- USB原配线数据接线未证，普通模式未枚举；Wi-Fi没有本机链路证据。旧NOR逐扇区日志路线已退役，未先证明可靠性/吞吐改善就不重开。

改动后`just check`、`uv build`，按真实结果更新现有报告再commit/push。Ubuntu接手后它是本阶段代码/证据的权威工作树；Mac只fast-forward同步，避免两边修改同一功能。
