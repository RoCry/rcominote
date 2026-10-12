# 固定映射系统镜像导出

最新验收（2026-10-12）：1811个正文chunk已全部读回，发布927632 B mapped-system.bin；头SHA与正文checksum通过，并由`comi image inspect`独立复检。[完整验收记录](evidence/mapped-system-complete-2026-10-12.json)、[离线分析入口](offline-system-analysis.md)。以下保留各阶段实验；早期“未完成”描述属于当时边界。仍非raw NOR或可恢复整机备份。


2026-10-12，C261CF0430/FW010004。**映射镜像导出工具已实现；完整正文校验与原厂恢复尚未验证。** 不依赖App登录。

## 已验证与失败证据

- 头部固定SHA256 `911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5`；每次会话重新读取，并在读取正文前验证。
- 正文起点`10000200`，声明长度927120 B；终点exclusive `100e2790`。固定1811块，每块512 B、末块400 B。
- 首四块连续读取两次，2048 B全部一致：[首次](evidence/body-probe-first-2026-10-12.json)、[复读](evidence/body-probe-second-2026-10-12.json)。
- 64块会话未通过：第14块`10001c00`在`10001c60`只返回6字节后被日志打断；ACK/STOP完成仍不代表数据完整。[真实失败](evidence/image-session-truncated-2026-10-12.json)。工具拒绝保存该会话，未发剩余正文命令。
- 每会话8块（4 KiB）连续9次成功、保存36 KiB，但第10次在`10009a60`再出现6字节截断：[证据](evidence/image-short-session-truncated-2026-10-12.json)。缩小会话不足以消除单条长输出失败；现在每个512 B存储块改为两条256 B请求（末块256+144），分别help并验收。

## 使用与完整性

```sh
uv run comi diag capture body-probe --out artifacts/body-probe.json
uv run comi image export --directory artifacts/mapped-system --max-sessions 1
uv run comi image export --directory artifacts/mapped-system
```

`max-sessions=0`继续到所有块齐全。失败保留原始采集并非零退出，重跑复验已存记录并只读缺失块；不自动无限重试。每次连接验证既有logsrv入口/引用、512 B镜像头，每个mdb之后help并等待完整行才继续；不开放自由地址或长度。

`chunks/`保存原子发布的JSON记录，内容、位置、长度、SHA256同时提交。相同重试接受，冲突/损坏/未知文件拒绝；未发布`.part-*`不计进度。`captures/`保留实机协议证据。会话失败时不把其部分内容计入完成进度，最多重读该会话。

只有1811块齐全，且正文LE u32加和加头部`4e7a894a`模2^32等于`ffffffff`，才发布`mapped-system.bin`，927632 B。缺块不补零；已有输出必须与重新校验的完整镜像长度/hash一致，否则拒绝；一致时确认已完成，恢复发布后中断。

## 边界

即使完整校验通过，仍只覆盖当前映射system镜像；不是4 MiB原始NOR、其他分区、NVRAM或设备唯一参数的备份。没有写Flash、切ADFU、执行回调、复位或恢复操作。下一步先取得完整镜像校验，再离线追踪板级初始化、升级与签名验证代码。

校验算法来源：固定SDK提交`26f51e584940d5b141cd1d09d2629d69b595f579`，`bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c:178–255`，`run_off==0x204`且flags无`0x04`分支；本机实读头部flags=0、向量位于header后。与真实CoMi bootloader实现是否相同仍待反编译，不据此推断关闭安全启动。[已读头部](image-header-readback.md)。

## 256 B试读与范围重叠修正

256 B请求已保存额外8 KiB，随后遇到工具误报：正文经过`1000bf20`，与会话前置guard重复；旧解析器在整个会话中搜索地址，错误拒绝合法第二次读取。[误报原始采集](evidence/image-overlapping-guard-2026-10-12.json)。

修正：每条读取记录响应frame起止；等待和最终验证都限定本条请求的范围。正文与guard均独立完整验收，再比较重叠内容；仍拒绝同一请求内重复/缺行。保留guard原有非对齐短读取语义，不能套用正文16 B对齐限制。[修正后真实重叠读取](evidence/image-scoped-overlap-2026-10-12.json)。这次误报与前述512 B真实截断是两类问题。

## 当前停止点

累计持久保存52 KiB正文；已实测跨进程续读、guard与正文重叠校验。256 B仍出现真实截断：`1000d900`请求只到`1000d9c0`，末三行缺失；工具拒绝整个会话，既有块不受影响。[256 B失败](evidence/image-256-truncated-2026-10-12.json)。因此不宣称可靠全镜像导出；下一步核对shell执行与日志刷新时序，不能仅靠继续缩短连接解决。

已实现离线存储、范围与终检门槛；完整镜像checksum、原始NOR备份和烧录仍未完成。App登录按用户要求暂不推进。

## 继续：缓冲计数器回绕与小块读取

进一步对照源码与已保存实机指令，确认8位队列计数器回绕时无符号比较可误判满队列，丢弃输出尾部；详见[日志缓冲回绕](log-buffer-wrap.md)。250 ms读取后等待试验仍在504 B边界截断，没有采用该延时。

正文传输改为每条64 B（4行约316 B文本），每条之后help刷新并验收。512 B本地持久化块不变；最后400 B按6×64+16读取。64 B试读连续8会话、512条正文请求通过，新增32 KiB，累计88 KiB；随后继续导出。镜像头也改为8×64 B，拼接后仍必须匹配同一SHA256。历史`header-batch`/`body-probe`保持其明确512 B诊断含义。

这不是修改设备固件；小于504 B的mdb文本先进入缓冲，后续help承担推进帧的输出。仍严格拒绝任何不完整数据，不把已知缺陷当作放宽验收的理由。完整镜像校验未完成前，保留部分导出状态。

## 16 KiB会话验证

64 B请求稳定后，默认每会话由8个存储块改为32个（16 KiB），单条读取/头部/逐行验收不变。两次实测全部完成：分别44.390/46.809秒、3176/3173个notification、534 ACK且F1完成；通知数低于8192上限。计时含发现、guard、头部、help与STOP，不是纯payload吞吐率。[范围/hash/计时证据](evidence/image-session32-analysis-2026-10-12.json)。

对照先前4 KiB样本17.320秒/870 notification；较大批量减少连接与重复验证次数，但失败时最多需重读本会话16 KiB。两个大批量试读后累计保存324 KiB，随后已按新批量继续完整导出；不能把这些分段成功等同全镜像校验通过。

[离线校验与分析入口](offline-system-analysis.md)：`comi image inspect PATH`共用完整镜像校验；Ghidra脚本只接受通过校验的固定系统镜像。完整成功路径仍待实机文件到齐。
