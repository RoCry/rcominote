# 启动反编译：不返回契约与函数边界

2026-10-12；C261CF0430/FW010004完整映射镜像SHA `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。离线分析，不执行目标、不修改设备。

## 实际调用与模型依据

[bytes及逐指令证据](evidence/startup-noreturn-analysis-2026-10-12.json)：

- kernel入口`1009aa54`最后BL `1002d260`，后接NOP和literal。自动分析把callee当可返回，继续解码literal，产生伪造的coprocessor/jumptable尾部。
- `1002d260..1002d2a2`切换PSP、恢复中断、把传入entry放r0，r1–r3清零后BL `1009ffba`。
- `1009ffba..1009ffce`保存entry、调整三个参数并BLX entry；entry返回后BL `1009c054`、BL `1002d850`。无正常函数epilogue。
- `1009c054`从`[18037a24+8]`取得对象；`1002d850`对同一全局对象比较，处理异常上下文后尾调用`1009c080`。

这与固定SDK [z_thread_entry](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/lib/os/thread_entry.c#L26-L46)的entry→current getter→abort current thread及`FUNC_NORETURN`契约对应。符号身份和不返回语义属于实际调用结构支持的源码匹配；没有实测线程终止，也未完整展开abort调度实现。

## Ghidra约束

`SystemImage.java`按下游→上游设置五个已知范围，末地址不含：

| entry | end |
|---|---|
| `1009ffba` | `1009ffce` |
| `1002d260` | `1002d2a2` |
| `1009aa54` | `1009ab0a` |
| `1002d0c4` | `1002d11e` |
| `1002d818` | `1002d84c` |

明确函数body并标注no-return；仅在`1009ffca`这个“abort当前线程”call site应用`CALL_RETURN`终结控制流。没有把通用abort函数标为不返回：它作用于其他线程时可能返回。`CALL_RETURN`是分析模型的终结表达，不声称原始BL指令本身是tail branch。

导出前检查五个函数no-return标志及末地址，漂移即失败，不发布C文件。扩大为21个指定入口，新增线程入口和切换函数。其余函数的类型/参数仍由Ghidra推断；不把伪C当原厂源码或运行证据。

## 实测验收

Ubuntu真实镜像重跑通过：分析58秒，21个入口导出，五处函数边界检查通过。[产物SHA与结果](evidence/startup-ghidra-bounded-2026-10-12.json)。kernel入口不再出现literal引起的coprocessor/jumptable伪尾部；thread wrapper不再延伸进下一个函数。首次仅设置no-return仍使thread wrapper延伸，本次增加具体call site终结修复该失败。

仍有伪C限制：entry间接调用显示5个参数，而实际指令只搬运3个；`CALL_RETURN`可能呈现结构性的`return`，不证明该调用能回到原调用者。类型/ABI和执行行为仍以原始指令为准。本轮校正的是控制流边界，未宣称恢复全部原型。
