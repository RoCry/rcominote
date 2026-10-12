# 正常态 RAM 执行入口：有界静态盘点

2026-10-13，host-only；无设备 I/O、写内存、handler 执行或控制流破坏。
**现有日志 code-TLV 不是代码上传协议；已枚举的实际 shell 静态树没有声明任意 RAM 调用/加载后执行命令。**
有内存写入和 `devmem load`，但未建立分配、上传、缓存同步、入口 ABI、返回或独立退出合同。关闭“正常诊断接口已提供 RAM 执行器”的假设，不声称整个固件不存在其他入口。

## 输入与覆盖

使用此前完整取得的 [system gzip](evidence/minimal-image-2026-10-13/original-system.bin.gz)：解压927632 B，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。
[紧凑证据](evidence/normal-ram-entry-2026-10-13.json)保存全部表项、完整字符串、所审直接代码和独立 literal 区域；Python struct / Capstone 离线解码，未使用 REA provider 或声称 REA Evidence。

沿[已实读的 registry 合同](shell-registry-readback.md)，固定 root `100ba674..100ba6dc`，8 B stride，共13项；descriptor 为20 B。
本轮从完整镜像读取所有静态子表至真实 NULL syntax terminator：15张子表、81项子命令，全部 selector 的 dynamic 字段为0。嵌套展开仅针对表，不递归分析全部 handler。
Root 名称：`actlog/app/bt/clear/coredump/dbg/devmem/help/history/kernel/resize/shell/system`。

## code-TLV：控制码，不是机器码

实际 `1000c25e..1000c2c8`：type0 要求长度2，合成16位数后 `SXTH`；以下六个值进入固定分支，其他值回 TLV 循环。

| opcode | 实际作用 |
|---|---|
| `01` | `ctx[4] |= 2`，PREPARE 标志 |
| `10/11/12` | `ctx[6] = 1/2/3`，选择日志类型 |
| `20` | `ctx[6] = 0`，默认日志 |
| `21` | `ctx[6] = ff`，停止日志 |

这段路径没有取得入口地址、复制程序或跳转用户地址。实际 switch **没有 `13` 分支**；不能照搬参考 SDK 的 RAMDUMP opcode。
type1 才走文本：`1000c2cc..1000c306` 截断并 NUL 终止，安装输出 callback，调用固定 `shell_execute_cmd` 对应入口 `100a0e1a`，随后解除 callback、发送日志。
上述是实际代码的路径边界，不代表模式更新和 dump 的下游无副作用。

## 容易误判为执行器的命令

| 实际入口 | 完整直接路径支持的结论 | 未建立的合同 |
|---|---|---|
| `dbg mwb/mwh/mww` → `100a1857/185d/1863` | 选择1/2/4 B宽度，尾跳共同 `100a17f4`；解析地址/值/可选count，STRB/STRH/STR循环后返回 | 只是任意地址填写；没有分配、调用地址或执行完成回执 |
| `devmem` → `10022bfd` | 参数地址的8/16/32位直接读写，完整handler `10022bfc..10022cb6` | 不验证写入目标是否空闲，不提供执行语义 |
| `devmem load` → `10022d15` | 解析目标至全局 `1800c088/1800c090`；安装**固定** `10022df9` callback。`100a0e84..100a0e8a` 只存callback到shell ctx+38 | 安装接收回调不等于调用上传地址；BLE文本接口是否能向此 bypass 提供原始输入未证明 |
| 固定 bypass `10022df8..10022ef4` | 十六进制字符解析、逐字节存储；识别 `18 11` 转义组合，解除bypass，按选项处理字节序，然后返回 | 该转义仅是流处理退出，不是硬复位；没有候选入口调用或通用上传边界保证 |
| `dbg reboot` → `10024dcd` | 参数只比较固定 `adfu/poweroff/jtag`；调用已有重启/关机路径 | 不是任意RAM entry；本轮不重新审计其下游，更不证明ROM模式可退出 |

`dbg` 共35项，NULL descriptor 位于 `100bbb90`；没有 `call/go/exec/run` 或声明加载后执行的项目。`devmem` 唯一子项是 `load`。
其他表中的配置、音效、蓝牙测试、日志/内存导出名称均已记录，但未逐个审 handler；不能据名称排除其全部隐藏行为。
参考 SDK 的 [devmem_service.c][devmem] 与上述实际直接路径相符，只用于语义交叉核对，实际地址和结论来自镜像。

## 路线结论

正常态 RAM **写入**与正常态 RAM **运行**是不同能力。当前没有受支持的加载后执行合同；不以修改callback、栈或返回地址填补缺口，也不为寻找这种方法展开全固件间接调用扫描。
没有本轮证据允许执行[自建M4镜像](minimal-firmware-image.md)。后续继续匹配加载/ROM材料及独立退出路径；仅在取得新的明确入口、配置或厂商协议时重开本路线。

[devmem]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/devmem_service.c#L33-L243
