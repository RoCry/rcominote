# 显式NOR SDFS：目录偏移、文件读取与错误行为

2026-10-12；FW010004。[实际字节](evidence/sdfs-nor-read-path-2026-10-12.json)与[离线指令模拟](evidence/sdfs-read-emulation-2026-10-12.json)。无Flash API调用或设备I/O。

**`/NOR:K/`走显式分区Flash读取，不是默认SDFS映射内存复制。文件起点取目录相对offset加分区offset。实际sd_fread把底层错误转换成0，与EOF共用返回值。** 因此未来导出不能仅以“读到0”作为成功结束。

## 实际目录查找

`100266b8..1002679a`是sd_fopen的显式分区片段。对应固定SDK的[非XIP NOR目录实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/sdfs/sdfs.c#L101-L158)，但以下字段与流程均由实际指令支持：

1. storage0、part+10查分区表；K→file ID20，见[DSP资源路径](dsp-resource-path.md)。
2. 取分区entry+c作为offset，经`100a1b94`读32 B头部。负返回进入失败路径。
3. 比较头部首8 B与`sdfs.bin`；header+c作为目录项数N。
4. 分配`(N+1)*32` B，重新从同一分区offset读整个目录；失败释放buffer。
5. 跳过首32 B头，逐项32 B，调用大小写无关的12字节名称比较。
6. 匹配项+c加分区offset；构建16 B file对象：+0=start，+4=size（目录项+10），+8=read cursor，+c=storage byte，+d=part byte。

目录未取得，故不能把N、DSP offset或文件长度填成实际值。此片段也未显示将目录长度或文件extent与分区size比较；未来离线解析/导出需要独立边界校验，不能信任损坏目录给出的长度。

## 实际读取与设备绑定

完整`100267ec..10026848`：

- 按size与cursor把请求长度裁到剩余字节；非正长度返回0。
- storage非0返回−1。
- part=ff调用内存复制；显式part则以cursor为offset调用`100a1b94`。
- 底层返回非负，cursor加本次长度并返回长度；负返回打印错误并返回0，cursor不变。

完整`100a1b94..100a1ba2`只取device+8的API表首slot并尾调用，保留四参数。全局device pointer来自`1800e000`；初始化片段`10026a04..10026a10`绑定字符串`spi_flash`并存入该global。这与[此前NOR对象/底层审计](nor-driver-readback.md)一致，但本轮未观测global的运行时值或执行下层driver。

在本层未发现文件解压/解密；不能据此推断底层、镜像打包或原始Flash字节关系。已有NOR审计仍保留地址模式切换等边界。

## 可复现的错误验证

```sh
uv run tools/verify_sdfs_read.py artifacts/mapped-system/mapped-system.bin
```

脚本SHA绑定原镜像，执行实际sd_fread指令，仅拦截Flash接口和日志；每次最多1000条指令，遇未知执行地址立即失败。手工oracle：虚拟文件5 B，起点240100，cursor240102，请求8 B。

| 场景 | 实际结果 |
|---|---|
| 尾部短读，底层成功 | 请求裁成3 B；返回3；cursor240105 |
| 同一对象再次读 | 返回0；无Flash调用；cursor不变 |
| 底层返回−5 | 返回0；cursor240102不变 |
| 失败后重试同一对象 | 再次调用相同offset/length；仍返回0 |

这是原始ARM函数行为测试，不是Flash、目录或DSP资源实测。未来导出至少须对照可信文件长度、实际累计字节数和读回一致性；不能把这套模拟作为备份成功证据。现有CLI仍未获得该资源：shell的printk正文回传限制见[读取通路](readback-routes.md)。

后续[原始分区读回](nor-partition-prefixes.md)：system前64 B双读与映射头不同；NOR K的256 B目录双重校验，定位aerecord.dsp绝对offset24d400、size1ae44。文件正文与恢复仍未验收。
