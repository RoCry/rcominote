# 普通USB数据功能：本轮验证与下一步

2026-10-13。用户将USB文件传输、U盘模式列为研究重点。
目标先回答原厂固件能否通过磁吸口导出录音；ROM烧录另行判断。

## CLI现状

- `uv run comi info`能读当前模式；`call`为通话，`memo`对应NOTE。录音响应/文件类型也有各自模式字段。
- 目前**没有NOTE/CALL切换命令**；[固定App的23个请求](remaining-client-contracts.md)没有已确认的设置项。说明书给出物理双击电源键路径，不自动等于可通过BLE注入按键。
- `uv run comi settings set usb on|off`设置USB_COPY配置并要求读回一致；不是已建立的U盘启动命令。
- `uv run comi usb snapshot|diff`只观察Mac已有USB描述符，不传输文件或操作磁盘。

## 新的线材事实与实机结果

用户本轮确认：**原配整根四触点磁吸线连接本Mac，但尚未验证整根线能传数据**。
这比旧记录“已确认数据线”更具体；[历史插拔负结果](usb-log-probe.md)仍有效，
但不能据此排除磁吸线未接数据脚。四个触点与USB电源/数据布局相容，针脚定义仍是待证假设。

[本轮实机摘要](evidence/usb-settings-live-2026-10-13.json)：

| 检查 | 结果 |
|---|---|
| 精确设备 | C261CF0430 / FW010004，开始idle、charging、CALL、USB_COPY=true |
| 已有CLI往返 | USB_COPY on→off→on，两个setter均通过字段读回；回复00不额外赋予ACK语义 |
| Mac描述符清单 | 三次各16个节点；before→off与off→on的added/removed/changed均空 |
| 最终状态 | 完整info等于初始；idle；USB配置已恢复on |
| 录音 | 前后完整8项列表相同；没有录音、删除、格式化或下载文件 |
| 被动事件 | 独立3秒watch无事件；不是连接状态或拔插行为证明 |

原始清单/文件名留忽略目录`artifacts/usb-followup-2026-10-13/`，公开摘要不含其他USB设备身份。
未物理重插、重启、打开USB设备handle、挂载磁盘、进入ROM或写固件。
配置setter可持久化NVRAM；不声称本轮没有任何NOR写入。
结果只排除“在本次连接状态下切换该配置立即产生可见USB接口”，不排除重插/启动门控、其他固件或维修线。

随后用户将磁吸线换到另一接口，本轮重新采集主机树并读取CoMi状态：
仍16节点，与恢复on时完整清单相同；本机idle、charging、USB_COPY=true、CALL。
另查询最近5分钟macOS USB枚举/连接/失败日志，命中19项；可辨识设备均为此前
确认的另一台`rcwodle console`，含失败记录的同端口为`00120000`，不能归给CoMi。
没有从这份过滤日志建立CoMi枚举尝试，亦不把日志缺失当成电气层无数据的证明。
此后续只观察主机与读设备状态，没有再次切开关或重启。摘要已追加同一证据文件。

## 明确验证on后重插

用户提出插入时才读取配置的假设，新增[完整对照摘要](evidence/usb-replug-live-2026-10-13.json)。
已有恢复on发生于本地08:50，用户换接口后的采集为08:53；那次已覆盖一次类似重连，
但未采集断开时的CoMi充电状态。本次补齐该中间状态，Mac端接口保持不变：

| 阶段 | CoMi充电 | USB_COPY | 录音状态 | Mac完整USB清单 |
|---|---|---|---|---|
| 连接基线 | true | on | idle | 15节点 |
| 用户只取下磁吸头、尚未接回 | false | on | idle | 同一15节点，无任何差异 |
| 用户接回，无USB/传输提示 | true | on | idle | 同一15节点，无任何差异 |

`settings set usb on`走`already_matches`，本次未发送setter；随后均为正常只读查询。
重新连接后8项录音列表与上一轮最终完整列表相同；本次未另取拔下前文件列表，未比音频字节。
最近3分钟、按USB枚举/连接/失败关键字过滤的主机日志0项；不据缺日志推断电气层无活动。
原始树、状态、文件名与日志留`artifacts/usb-replug-2026-10-13/`。

**当前线材/接口/FW下，on→明确断开→接回仍未产生可见USB数据接口。**
这关闭“只差重新plug一下”这条简单实验；不证明磁吸口没有数据脚、不排除启动时门控或其他固件模式。
没有关机/重启、ROM入口、磁盘挂载或固件写入请求。没有新线材/入口证据时不再重复该插拔序列。

## 参考SDK确实有U盘功能，但本机还缺启动闭环

固定源码[`lv_port_actions_technology@26f51e5`](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579)：

1. [`CONFIG_USB_MASS_STORAGE`编译门](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/CMakeLists.txt#L3-L13)选择MSC实现；[独立card_reader应用](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/CMakeLists.txt#L24)另有配置门。
2. [card_reader初始化/退出](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/card_reader/card_reader_main.c#L131-L165)先卸载本地文件系统，再初始化USB MSC；退出后重新挂载。自写固件应维持同一存储的所有权切换，不能简单在正常录音期间再开放同一可写磁盘。
3. [MSC初始化](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/mass_storage.c#L1931-L2008)注册描述符、配置USB并enable；[磁盘初始化](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/mass_storage.c#L1744-L1795)按disk号取得介质容量；正文通过disk_read/disk_write访问后端。

这是可复用的软件结构，不是已匹配CoMi的M4 BSP或运行证明。
本机已有[CDC初始化/描述符](usb-cdc-config.md)和[MSC弹出状态getter](usb-msc-followup.md)；
应用CDC是生产测试接口，不能当文件传输端口。
[本轮实际固件追踪](usb-normal-mode-followup-2026-10-13.md)进一步检查USB_COPY消费者和连接消息，
仍不能把配置字段、MSC字符串直接当成已建立的MSC→录音SD后端。

## 优先级和停止条件

1. **线与触点**：确认原配磁吸线的数据接线/针脚资料；若需通断测量，应完全断开设备与USB电源后测线材，不向未知触点加电。没有这个事实，再换操作系统或重复切开关不能区分线路和固件。
2. **原厂普通模式**：从现有完整system定位USB连接事件→应用切换→class初始化→存储后端；取得具体入口后才做有问题意识的重插/普通开关机试验。静态链断在何处就记录何处，不递归新增零散实机代码读回。
3. **实际枚举**：一旦有可归属节点，先读VID/PID、interfaces/endpoints，再分MSC/CDC/vendor协议。若MSC出现，先确认LUN与容量，再做受控只读文件访问；“显示64GB录音盘”不等于可读4MiB固件NOR。
4. **自写固件**：匹配M4 BSP、USB PHY接线、SD后端和可恢复运行入口齐备后，可沿SDK结构实现MSC。当前不能靠CLI让原厂固件凭空新增USB class。
5. **烧录/恢复**：ROM ADFU是独立路径。即使普通U盘模式跑通，也不自动解决原厂恢复包、完整NOR备份和独立退出条件。

不新增循环枚举、猜测私有opcode、设置USBCDC_TEST_MODE或ROM试探；
在新针脚/线材/启动入口证据到来前，保留已有CLI和本轮结果即可。
