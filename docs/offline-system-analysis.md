# 当前系统镜像：离线校验与分析入口

2026-10-12。对象为C261CF0430/FW010004的固定mapped-system镜像；与公开SDK `adfus.bin` helper分开，不执行目标代码、不连接设备。

## 验收边界

- `uv run comi image inspect PATH`：长度先验927632 B，头512 B必须匹配已读SHA，正文927120 B按ACTH的LE u32加法checksum验证；输出完整SHA与scope。与导出finalize共用实现，避免两个校验规则漂移。
- 截断、多余字节、错误头、错误正文均有离线拒绝测试，oracle为实读头与实际字段。没有构造伪造checksum成功镜像。
- Ubuntu实测把公开56108 B的adfus.bin误传给系统镜像入口：明确报927632 B长度不符、非零退出，未创建分析目录。远端repo已fast-forward同步，工作树干净。
- 完整实机镜像已导出并独立离线复检：927632 B，1811个正文chunk；SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。正文u32和`b18576b5`加头内checksum `4e7a894a`恰为`ffffffff`。[验收记录](evidence/mapped-system-complete-2026-10-12.json)。Ubuntu Ghidra实跑通过，见下文。
- `SystemImage.java`已用Ubuntu现有Ghidra12.1.4/JDK21.0.12.1+1的真实类库编译通过；随后真实headless运行也已完成，编译验证与运行验证分开记录。

## 重现

```sh
uv run comi image inspect artifacts/mapped-system/mapped-system.bin
bash tools/setup_re_tools.sh
bash tools/analyze_system.sh artifacts/mapped-system/mapped-system.bin artifacts/system-ghidra-NEW
```

最后两步在Linux x86_64执行，使用[既有固定工具版本及SHA](offline-helper-analysis.md)。脚本在创建输出前执行完整镜像校验、检查工具并拒绝已存在的输出目录；任一失败即退出。拒绝覆盖旧分析目录。

Ghidra：BinaryLoader，base=`10000000`，语言`ARM:LE:32:Cortex`，Thumb context。模型由实际向量/指令约束，不凭语言名称认定芯片。单个`SystemImage.java`维护entry清单：preScript seed；postScript export，避免两份地址清单漂移。保存project、analysis.log和选定函数C；必须实际取得全部选定函数的非空反编译结果才发布C文件。

## entry依据

- 日志stream wrapper/sender/saver/traverse callback及timer：来自[实际日志链](log-buffer-wrap.md)及[回调入口](shell-service-readback.md)。
- shell内部执行、backend getter/注册、sdfs/partition getter：来自[文本执行](shell-text-readback.md)、[分区读取](partition-readback.md)。
- reset/prep/IRQ初始化，及直接BL目标bss/data/cstart/memcpy/memset候选：来自[启动入口](reset-entry-readback.md)。未读取callee时只把它作为entry候选，源码符号对应仍是推断。
- 默认日志callback `1009ef2c`：实读注册参数的Thumb指针；[body已确认](log-buffer-wrap.md)，直接尾调用saver。

初版清单19个入口/调用目标；[启动边界修正](startup-noreturn-model.md)后增加2个已证实调用目标，共21个。不加入任意猜测入口，不把推断类型、伪C或间接调用关系视为运行证据；关键结论仍需与原始指令及数据交叉核对。完整映射镜像即使校验通过，也不代表原始NOR、全部分区或可恢复备份。

## 真实镜像headless验收

Ubuntu运行脚本成功退出；Ghidra报告分析58秒、import/analysis/post-analysis/save成功，19个指定入口均取得非空C输出。[验收及产物SHA](evidence/system-ghidra-acceptance-2026-10-12.json)。本地ignored产物`artifacts/system-ghidra-20261012.c`及同名`.stdout`；Ubuntu保留project。没有执行目标固件。

交叉核对：ring saver的unsigned差值判断、默认callback到saver、memcpy/memset逐字节循环与Capstone实读指令相符。**生成成功不等于伪C全部准确**：kernel entry自动函数范围越过已知`1009ab0a`，把literal/后续字节卷入并报jumptable警告；部分调用签名参数数目也推断错误。该尾部不作为启动行为证据。后续分析应先校正函数边界、non-return调用和签名，再使用高层伪C；现有结论仍以带bytes的报告为准。

后续已完成[具体调用点no-return建模与真实重跑](startup-noreturn-model.md)，修正启动literal误反编译。旧19入口验收记录保留；当前21入口工具以新增验收为准，参数类型推断限制仍在。
