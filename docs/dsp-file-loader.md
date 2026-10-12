# DSP文件加载器：540 B头部与分段读取边界

2026-10-12，FW010004离线分析。[实际字节](evidence/dsp-file-loader-2026-10-12.json)、[Unicorn结果](evidence/dsp-header-emulation-2026-10-12.json)。未取得DSP文件、未执行设备或DSP代码。

**实际主加载器检查540 B头部及魔数，按code/data指针加载分段。它不是完整镜像校验器：空section指针也能返回成功，且初始seek错误未被检查。** 这些行为不证明官方DSP文件有问题，而是限制后续备份验证能依赖什么。

## 主文件头

完整函数`1003caf4..1003cb66`与固定SDK的[文件加载实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/dsp/dsp_image.c#L214-L261)对应，直接调用点在`1003cbb0`。实际流程：

1. 调`1002ebf4(file,0,0)`，未分支检查返回值。
2. 调`1002eb5c`请求`0x21c`（540）B；无符号返回值比较，小于540报invalid image并返回−22。
3. 头部首word必须`0x79716878`，磁盘小端字节为`xhqy`。不能把宏参数`y,q,h,x`直接当磁盘字节序。
4. +14 word为code section表offset，非零调用`1003c914(file,offset,1)`；+18为data offset，非零以第三参数0调用。任一失败返回−22。
5. output非NULL时写头部+10的entry point，返回0。

字段offset为十六进制。固定[IMG_filehdr布局](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/dsp/dsp_image.h#L182-L215)还包含版本、类型与64组bank指针；本轮没有审计bank加载，也不把这些字段声明为已完整校验。

## 分段读取

完整`1003c914..1003ca36`：offset按有符号比较，非正直接成功；正值先seek，非零返回−5。

- 每轮请求8 B section头（size、DSP目标地址），但实际比较只要求读回值无符号大于3；size=0结束。**不能把这写成要求完整8 B头部。** 非零size的4..7 B短头可能使用未完整更新的地址字段；本轮未执行此异常分支。
- 目标地址通过内联映射逻辑转为MCU地址，失败返回−14。该逻辑与地址周围MMIO操作仅静态分析，未执行或测量。
- 请求size B数据直接读到转换后目标；返回值无符号小于size则报错返回−5，否则继续下一section。
- 本函数未显示整文件哈希、签名或分段checksum比较。不能据此推断启动安全策略，或所有加载阶段都无认证。

前篇[SDFS读取](sdfs-nor-read-path.md)将底层错误转为0；这种0在非空段读取中会触发长度检查。泛化到其他后端时仍须注意上述无符号比较，不能只照抄固件条件做导出验收。

## 可复现测试

```sh
uv run tools/verify_dsp_header.py artifacts/mapped-system/mapped-system.bin
```

脚本SHA绑定原始ARM镜像，执行主加载器；拦截seek/read/log，拒绝其他外部执行，1000指令上限。手工合成头部依据固定SDK布局，code/data/bank指针均0，entry为哨兵12345678；**不是设备DSP文件**。

| 输入/过程 | 验证结果 |
|---|---|
| 540 B、正确魔数、空sections | 成功并复制entry |
| 539 B短头 | −22，entry不变 |
| 540 B错误魔数 | −22，entry不变 |
| seek返回−5、随后read仍提供完整头 | 继续读取并成功 |

因此未来提取后的检查应包含可信长度/边界、完整目录和文件读回一致性，以及实际section内容；仅运行主加载器或看到正确魔数不足以宣称可恢复。资源取得仍受现有读取通路限制，见[DSP分区](dsp-resource-path.md)。
