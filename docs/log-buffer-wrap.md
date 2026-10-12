# 日志ring计数器回绕：实机代码证据

2026-10-12；C261CF0430 / FW010004。仅分析已有映射镜像chunk；无设备I/O、写入或复位。

**已确认：实机日志ring的满判断存在8位计数器回绕错误。** 这提供了完整协议帧、ACK和F1均正常但文本尾部消失的具体机制；没有失败瞬间的rd/wr快照，不能把所有丢字节都归因于它。

## 证据与代码身份

[逐字节、SHA及完整反汇编](evidence/log-buffer-wrap-analysis-2026-10-12.json)。输入来自`artifacts/mapped-system/chunks`不可变JSON记录；每条的长度、bytes SHA及已知512 B头SHA经`ImageStore`验证，再按实际地址拼接。JSON保存输入chunk记录的文件SHA与bytes SHA，保留复核关系。完整镜像正文校验仍未完成。

| 地址/长度 | 代码或数据及身份依据 |
|---|---|
| `1000c2e6` /34 B | 已读TLV文本分支：注册callback→shell执行→解除callback→BL `1000bc18`；来自[既有调用链](shell-text-readback.md) |
| `1000bc18` /204 B | 帧发送器：读取rd/wr、slot编号mask7、打包`1d f0 81`及TLV长度、调用`1000bb5c`、清slot并递增rd；完整算法对应SDK sender |
| `1000bb5c` /52 B | 调`100517fc`后比较返回值与请求长度；不等返回-5；下层callee未覆盖 |
| `1000bcec` /192 B | ring保存函数：锁、满检查、504 B空间、复制、更新slot长度/wr、返回实际复制长度 |
| `1000bdb0` /84 B | 遍历callback：`1000bdca`直接BL `1000bcec`；复制不足时`1000bdec`直接BL sender，随后按已复制长度推进并重试 |
| `1000be8e` /36 B | 模式切换清理片段：清16 B slot长度，`rd=wr`，保留计数器当前值 |
| `1000bce4` /8 B，`1000bdac` /4 B | sender/saver引用的buffer base均为`1800a9b0`；另有drop格式串指针 |
| `1000c368` /4 B | TLV文本分支注册的callback指针`1009ef2d`，Thumb代码地址`1009ef2c`；现已读取20 B正文，见下文 |

函数名来自完整行为与SDK对照，未取得原厂符号表。保存函数的身份由明确的直接调用、返回复制长度和重试控制流建立，未按“靠近某符号”猜测。已知shell文本路径直接链接sender；实际默认callback到saver的直接尾分支现已确认。

关键region SHA256：

- saver192 B：`1ae8576e933758c351f6e2ac085a2b2a3adff1fafe89876b7d24e0c2b281cd4d`
- sender204 B：`c150a52e8adbddfa79727723301351389c83f9bc98a3902689fe93f2fad621de`
- traverse callback84 B：`269725efc91416b7c8fe9026548fcc5b9b12e05817945a2966a4f0d9b7ced798`

## 实际错误指令

下列bytes直接来自已验证chunk；其余完整指令见JSON。Thumb默认little-endian。

| 地址 | bytes | 指令/作用 |
|---|---|---|
| `1000bd0e` | `217a` | `ldrb r1,[r4,#8]`：wr，0..255 |
| `1000bd10` | `e379` | `ldrb r3,[r4,#7]`：rd，0..255 |
| `1000bd12` | `cb1a` | `subs r3,r1,r3`：32位差值，**没有收窄为u8** |
| `1000bd14` | `072b` | `cmp r3,#7` |
| `1000bd16` | `0bd9` | `bls 1000bd30`：仅**无符号≤7**时继续保存 |
| `1000bd18..bd1c` | `04f11c0093f0f9f8` | 失败路径取ctx+1c并调用`1009ef12`；随后返回已复制长度；helper现已确认是带DMB的LDREX/STREX原子加一 |
| `1000bd30` | `01f00700` | `and r0,r1,#7`：8个slot |
| `1000bd38` | `4fea402e` | `lsl.w lr,r0,#9`：每slot512 B |
| `1000bd40` | `ccf5fc79` | `rsb.w sb,ip,#1f8`：payload容量504 B |
| `1000bca6..bcb0` | `e379227a0133dbb29a42e371` | sender递增rd后`uxtb`、写回byte；计数器会回绕 |
| `1000bea8..beaa` | `237ae371` | 清理时`ldrb wr; strb rd`，不把两者归零 |

例：初始`rd=wr=254`。保存两个完整slot后wr写回byte变0，rd仍254。减法得到`ffffff02`，无符号比较`ffffff02≤7`为false，误入满/drop路径；实际只占两个slot，尚有六个空位。初始255时，保存一个slot就能触发同一错误。

此时问题不在BLE帧长度：已入队的slot仍可完整发送；未入队的文本尾部在保存层被拒绝。sender随后把rd推进到wr，恢复正常。由于模式切换保留counter值，STOP/重新BLE会话不保证避开下一次回绕。

## 与公开源码的对应

固定SDK：`lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`。

- [ring定义](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L42-L47)：512−8=504 B，`LOG_BUFFER_NUM=8u`；[ctx](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L117-L134)的rd/wr为u8。
- [保存函数](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L457-L498)：`wr_idx-rd_idx>=8u`。u8先提升为int做减法，再被右侧unsigned转换；负差变成大unsigned。这与实机`SUBS/CMP/BLS`吻合。
- [默认backend callback](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L596-L601)丢弃实际复制长度；[traverse callback](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L548-L570)则drain/retry。后者与实机`1000bdb0`完整控制流相符，前者实机body现已确认直接尾调用saver，不含drain/retry。
- [shell调用](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L683-L707)同步执行命令后才发送日志；[UART transport](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_uart.c#L336-L340)调用已注册输出callback，不能向其返回已保存字节数。
- [sender](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L500-L540)的drop提示使用`os_printk`；本通路未证明其会转入BLE。因而BLE未见drop文字不能排除保存层丢失。
- [stream长度检查](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L263-L273)及[BLE分片发送](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/bluetooth/bt_manager/bt_manager_sppble_stream.c#L666-L709)是其他可能失败层；本轮没有反汇编实际下层writer，不能排除其独立故障。

## 两次实际失败

| 捕获 | 请求 | 实际文本结尾 | 协议结果 |
|---|---|---|---|
| [256 B失败](evidence/image-256-truncated-2026-10-12.json) | `1000d900` /256 B | 恰好2×504 B，`1000d9c0`行bytes后缺ASCII/换行，后续3行消失 | 随后help完整；ACK30、F1、pending为空 |
| [512 B失败](evidence/image-short-session-truncated-2026-10-12.json) | `10009a00` /512 B | 恰好1×504 B，停在`10009a60`部分bytes | 随后命令日志/help可见；ACK24、F1、pending为空 |

**推断：** 分别与起始counter254/255时的回绕机制精确相容。协议解析没有半个F0残留、help随后正常，不支持将这些记录简单解释为主机漏拼分片或“等待不够”。但没有counter快照，尚不能证明这两次一定由该bug触发，也不能排除普通ring满/其他输出层丢失。

## 有界后续

当前采集器将正文和头均拆成64 B请求，保持严格逐行验收、失败重试；这降低单次文本量，未修复原厂ring。异步日志/已有积压仍可能影响结果，不能承诺64 B永不失败。宿主多等一段时间不能修复同步保存中已发生的counter错误。

可在同一已知镜像范围内独立重读一个256 B块，对比单次256 B、两次128 B、四次64 B，每次帮助刷新并完整验收；限制尝试次数，保留失败捕获。此实验只读已验证映射范围，不改设备状态或任意跟随地址。

确认运行时归因仍需额外证据：已取得注册callback代码；若已有当前ctx指针的可靠读取链，可在失败前后限定读取rd/wr元数据。当前报告未执行这些步骤。

## 默认callback补齐（同日）

实际`1009ef2c..1009ef40`共20 B：输入buffer/length/context由r0/r1/r2调整为context/buffer/length；r3读取context+5的byte；恢复r4后以`6cf7d6be`直接尾分支至`1000bcec`。这补齐shell注册callback→ring saver的实机边，callback本体无drain/retry，也无复制长度检查。尾调用仍把saver的r0返回值传回调用者；仅凭此函数不能断言调用者如何处理返回值。

`1009ef12..1009ef2c`共26 B是原子加一：DMB、LDREX、加一、STREX失败重试、DMB、返回。结合saver传入ctx+1c，确认该失败路径确实递增计数器。两段完整bytes、SHA和指令已追加到同一证据JSON；不改变缺少失败瞬间rd/wr快照的边界。

头部四次64 B后才help的批次亦捕获缺行：740 KiB断点处，`10000040`请求缺`10000050`行，ACK17/F1仍到达；失败批未提交任何正文chunk，重新运行后继续增长。采集器现将头部也改为每次64 B后help并验收，复用正文已有机制；不承诺消除原厂bug或其他丢失。原始失败保存在ignored captures，派生测试证据保留实际frame与请求声明。

逐段头部刷新版本随后真实完成剩余139个正文chunk（5个数据会话），完整镜像checksum通过；首个头部独立会话与全部数据会话均逐行验收通过。[会话摘要](evidence/mapped-system-complete-2026-10-12.json)。这证明本次恢复成功，不把有限成功样本提升为永久无丢失保证。
