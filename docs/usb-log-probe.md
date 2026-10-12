# USB 对照与日志握手实测

2026-10-12；自有 CoMi `C261CF0430`，FW `1.0.4`。延续首轮资料后的第二轮实验。

**结果：正常模式仍未观察到 CoMi USB 枚举；Actions log PREPARE/ACK 已在本机验证。**
前者尚不能排除其他 USB 模式/线路问题，后者尚不能证明 shell、固件读回或 OTA 可用。

## USB：数据线确认、拔下、插回

用户确认使用可传数据的 USB 线连接本 Mac，按要求仅拔下 CoMi，再重新插入；重新插入时没有 USB/传输选项。
每一步由用户回报完成后采集，没有自动复位或切换 USB 模式。

| 状态 | IOKit 设备数 | 对照结果 |
|---|---:|---|
| 已接已确认数据线 | 16 | 基线；无明确 CoMi 产品名/序列号 |
| 用户确认仅拔下 CoMi | 16 | removed/added/changed 均空；通用 `05e3:0743 USB Storage` 未消失 |
| 用户确认重新插入，无传输选项 | 16 | 同端口 `00120000` 的 `38f4:fffe Hiveton App Serial` 变为 `38f4:ffff rcwodle console`；其他节点未变 |

Hiveton 在交接与前次研究中已确认为另一台设备；其本轮身份变化是并行设备活动/环境干扰，不能归因于 CoMi 插入。
最干净的证据是**插着 CoMi→只拔下 CoMi**之间无 USB 节点变化。不能根据“16→16”独立下结论，工具比较了位置、VID/PID、serial、接口/描述符。

插回后通过 Boyi `info` 再读到匹配序列号、`usb_mode=true`、charging、idle、版本 `010004`；
这说明应用配置位与实际主机枚举不是一回事。没有尝试 `SET_USB_MODE` 开关、进入 ROM/ADFU 或读取 USB Storage 的内容。

### 修正采集方法

当前 Mac 上 `system_profiler SPUSBDataType -json` 返回合法 JSON，但 `SPUSBDataType=[]`。
因此它的空结果不能表示总线没有设备。`ioreg -r -c IOUSBHostDevice -l -w 0 -a` 实际给出设备树。
原始 plist 含二进制 `UsbDeviceSignature`，`plutil -convert json` 报 `Invalid object in plist for JSON format`。
新工具直接用 stdlib `plistlib` 解析，仅输出物理设备和接口描述符：

```sh
./bin/comi usb snapshot --out artifacts/usb-before.json
# 操作者只拔下目标设备，完成后再采集。
./bin/comi usb snapshot --out artifacts/usb-unplugged.json
./bin/comi usb diff artifacts/usb-before.json artifacts/usb-unplugged.json
# 操作者插回目标设备，完成后再采集。
./bin/comi usb snapshot --out artifacts/usb-reconnected.json
./bin/comi usb diff artifacts/usb-before.json artifacts/usb-reconnected.json
```

工具不打开 USB handle、不发 control/bulk 请求、不复位。按 IOUSBHostDevice 节点去重，
避免把同样带 VID/PID 的 interface/driver 子节点重复计数。也支持 `--input-plist PATH` 离线重放；
`processed_at` 表示处理时间，重放模式不冒充原始采集时间。原始完整 USB 树含其他设备信息，留在忽略的 `artifacts/usb/`。

原始采集 SHA-256（用于本机留存证据校验）：

| 文件 | SHA-256 |
|---|---|
| `host-devices.plist`（已连接） | `b07e2b5abb25080a06f1488958bb703dddc1c887516dfde0211660cbabf9e860` |
| `unplugged.plist` | `0ab170dcc54a896c813e69e66c538ca3a6c464b4240aabbb2a15566ff941e941` |
| `reconnected.json`（归一化） | `c99b878e17f74351da219b5afb8bc0b5aad49fcb4640c7e88ff5d4df20169362` |

[测试 fixture](../tools/fixtures/README.md)保留实际 Hiveton 节点的最小描述符子集，复现二进制 plist 与接口重复 ID 两个问题；它不被当作 CoMi 身份证据。

## Actions log：固定 PREPARE 握手

使用 [`tools/log_probe.py`](../tools/log_probe.py)，严格匹配广播 serial，连接 log service，订阅 notify，
发送一次固定 PREPARE，等待最多 5 秒 ACK，然后取消订阅/断开。没有发送 console-text TLV、开启日志流、提取 dump、执行 shell 或重启。

源自固定 SDK `log_service.c` 的手工帧表：

| 方向 | 字节 | 解释 |
|---|---|---|
| TX | `1d 10 81 05 00 00 02 00 01 00` | svc 1d；cmd 10；param type 81；LE 参数长度 5；TLV type 00、长度 2、code PREPARE=1 |
| RX | `1d 10 81 07 00 7f 04 00 a0 86 01 00` | 同协议头；参数长度 7；ACK TLV 7f、长度 4、LE 值 100000 |

SDK PREPARE 分支只设置 `ctx->prepared=1`；断连清除该位。
ACK 由公共解析成功路径生成，不能据此推断 `shell_execute_cmd` 的编译条件、命令执行返回码或任意操作权限。

- [常量/结构定义](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L51-L109)
- [ACK 打包](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L428-L437)
- [PREPARE 与 shell 分支](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L639-L711)
- [断连清理](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L869-L905)

实际通知与预期 ACK 逐字节一致，原始记录见 [log-prepare-2026-10-12.json](evidence/log-prepare-2026-10-12.json)。
这是 SDK 日志协议相容性的实测增量，不能精确区分同软件家族中的芯片料号。

```sh
just log-probe --out artifacts/log-prepare.json
```

工具只提供此固定握手，无任意 payload/shell 入口；异常响应/超时保留通知证据并以非零状态退出。

## 下一步收敛

软件侧可继续隔离复现 Linux 应用编译，见 [构建可行性](build-feasibility.md)。
板侧仍需拆机丝印、USB D+/D−走线、测试点、原厂包；USB 负结果和 log 正结果都不能替代这些证据。
ROM、SDK DFU 和 J-Link 的不同边界见 [恢复传输研究](recovery-transport.md)。
