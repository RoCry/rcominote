# DSP资源路径：/NOR:K/aeRECORD.dsp

2026-10-12；C261CF0430 / FW010004，离线镜像分析。[字节证据](evidence/dsp-resource-path-2026-10-12.json)保留完整image creator、路径parser、SDFS open adapter及相关表；session只保留调用片段。无设备I/O。

**实际DSP image creator通过文件接口打开`/NOR:K/aeRECORD.dsp`。** 固件SDFS路径规则把K映射到file ID20；此前实机ACPT表对应`sdfs_k`，配置物理范围`0x240000..0x2f0000`、704 KiB。尚未读取该分区目录或DSP内容，不能声称文件已成功打开、存在或已备份。

## 库名到文件路径

[codec分派](recorder-codec-dispatch.md)选择库名`aeRECORD.dsp`，放入传给`1002b978`的参数+8。其片段`1002b9e6..1002b9fc`将参数+8传给`1002bcbc`，返回值存session+1c；参数+c非NULL时同样创建第二image。

完整`1002bcbc..1002bd20`与固定SDK的[dsp_create_image](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/framework/dsp/dsp_image.c#L15-L46)文件系统分支吻合：

1. 分配24 B对象，失败返回NULL。
2. 用格式`%s%s`、prefix=`/NOR:K/`及传入库名构造32 B路径buffer。
3. `1002bce2`调用`1002e978`，参数为image+4、路径、flag1；实际通用文件open函数通过mount ops分派，flag与SDK FS_O_READ对应。
4. open返回非零：记录`cannot find dsp image "%s"`，释放对象，返回NULL。
5. 成功：image+10写固定`0x1000`，image+0保存原库名pointer，返回对象。

**0x1000不是实测文件长度。** 此函数没有seek/stat来取得长度。不能据此只备份4 KiB，也不能由源码另一个`sd_fmap`分支推断本机直接使用映射pointer。

## K到分区表

完整parser `10026514..1002657c`支持`/volume:letter/filename`。实际volume表`100bbbbc`首项指向`NOR`，索引0；冒号后A..Z减`0x41`得到part。因此`/NOR:K/aeRECORD.dsp`产生storage0、part10、剩余文件名`aeRECORD.dsp`。

- 实际SDFS mount validator `10026580..100265c2`调用该parser，并以storage、`uint8(part+10)`调用分区getter`10027720`。
- SDFS ops表`100bbbcc`的open为`100a1c39`、mount为`10026581`。完整open adapter `100a1c38..100a1c62`把原路径传`10026614`，将返回handle存file对象。
- [此前实际sd_fopen链](partition-readback.md)已证明`10026614`解析路径，NOR显式分区分支以storage0、part+10查表。
- 因此K对应file ID20；[实际ACPT第15项](partition-readback.md)为`sdfs_k`，offset240000、sizeb0000、flags0。

以上证明固件路径规则与已有表的对应关系。未取得本次运行时mount列表或观测一次成功open，不能把静态后端关联写成实时读取成功。分区flags0也不单独证明文件未压缩、未加密或能够直接刷回。

## 备份与移植缺口

system映射导出是ARM系统镜像；目前没有覆盖`sdfs_k`的证据。备份/恢复清单应显式包含该区，不能只保存system后宣称已保留录音能力。

下一步：核对SDFS显式分区目录与底层读取实现、DSP文件头/分段加载约束，再判断能否建立可校验的只读导出。文件系统读可能进行地址或数据转换；它与原始NOR备份是不同验收项。还需独立验证恢复入口，才能推进试刷。

后续[原始分区读回](nor-partition-prefixes.md)：system前64 B双读与映射头不同；NOR K的256 B目录双重校验，定位aerecord.dsp绝对offset24d400、size1ae44。文件正文与恢复仍未验收。
