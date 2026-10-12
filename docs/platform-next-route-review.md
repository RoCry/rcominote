# 下一条平台材料路线：正式 DFP 索引的有界核查

2026-10-13。先与主线程讨论并确认范围，再检查两个 Arm/Keil 官方入口；host-only GET，无设备 I/O、安装、包执行、源码修改或联系厂商。

**未取得新的匹配 BSP、芯片头文件、SVD、ROM 长度或厂商包链接。** 本轮关闭“正式 CMSIS Pack 索引可能直接提供遗漏 LARK 整包”的当前检索，不重开泛搜。若现有 loader DWARF 确实保留成套寄存器结构，提炼其有来源的局部定义比继续搜索同义词更有价值；其覆盖由主线程独立核查，不将该提议写成已取得成果。

## 为何选择此入口

[既有来源报告](platform-source-followup.md)已确认 LARK Flash/SD ELF 的编译路径来自 `BAREMETAL_CMSIS/lark_sdk`，涉及 `lark.h`、`system_lark.h`、LarkHal；SDK 自带 Keil/JLink 编程资产。
因此，一个实际 Device Family Pack 若含 CMSIS Device 头、startup/system、SVD 或 PDSC memory 定义，可能补芯片层材料。**这些编译路径只支持查询动机，不证明厂商发布过 DFP。**

这与已关闭的公共 SDK Git 历史、Vela vendor 包泛搜及官方 CoMi 手册检索不同；范围限定为正式 Pack 索引和其直接厂商链接。没有匹配条目时，不猜下载文件名或扫描全部无关厂商包。

## 本轮实际取得的证据

| 官方入口 | 实际结果 | 证明边界 |
|---|---|---|
| [Keil 完整 Pack 索引](https://www.keil.com/pack/index.pidx) | HTTP200，经官方入口重定向至 [Azure 索引](https://sadevicepacksdqaus.blob.core.windows.net/idxfile/index.pidx)；XML完整解析 | 全部1823个 `pindex/pdsc` 条目、73个不同vendor；可核对包名/厂商/下载源属性 |
| [Arm Keil CMSIS Packs 页面](https://www.keil.arm.com/packs/) | localwebrs返回官方说明及首屏21个包项目 | 页面说明此格式分发组件、驱动和中间件；首屏不是全目录，**不作为全站缺包证明** |

完整 XML 身份：

- 字节数：`240268`。
- SHA256：`057c03b61aec6355845d4cfd8e948a54994674e55cb6efcf4dac952a0e9db8dc`。
- 索引内 timestamp：`2026-10-12T12:30:35.6917858+00:00`。
- 对全部1823条属性值进行大小写无关子串检查：`actions`、`ats3085`、`lark`、`gl6189`、`炬芯`，各为**0条**。检查覆盖 vendor/name/url/version 等已有属性；不是只看页面首屏。
- localwebrs先读取两个入口；随后对同一索引原始响应使用标准 XML parser 计数并计算原始bytes SHA，避免转换输出截断影响结论。

没有匹配条目，因此没有由该索引确认的 Actions 厂商 PDSC/`.pack` 下载链接可继续。未下载无关包，未建立正式设备包与 CoMi 的对应关系。
该结果只约束上述时间点的索引**元数据**；未遍历每个包内部设备清单，不能排除非公开包、未入索引包、异名包或后续发布。远端索引会更新，本页哈希标识本轮所见响应，不是假定永久快照地址。

## 路线判断与停止条件

1. **当前停止 DFP 获取。** 没有直接匹配包入口；不转为第三个搜索站点、猜测URL或重跑 SDK/Vela 来源搜索。仅在出现新的具体 PDSC/pack/厂商下载链接时重开。
2. **有条件优先现有成套材料。** 若两个未剥离 LARK loader 同时保留足够的 CMSIS 寄存器类型，且字段offset/size可以无猜测恢复，交付来源绑定的partial register定义并交叉核对。同名结构一致也只证明这两个参考产物一致，不证明 CoMi 寄存器语义或兼容性。
3. **提炼本身也有停止条件。** 若仅有软件状态、句柄和零散typedef，或必须猜base/IRQ/保留字段/bit语义才能拼成可用头文件，就记录缺口，不为新增脚本而转换格式。即使取得局部寄存器定义，仍缺匹配startup、时钟、内存/IRQ、板级配置及运行入口。

本轮没有为扩大 ROM 采集提供新的范围证据，也没有解除独立退出、完整备份或可恢复烧录的门槛。当前成果是可复核的获取边界；后续以实际新材料而非搜索次数决定进展。
