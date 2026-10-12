# CoMi DSP地址：实际映射与参考SDK差异

2026-10-12，FW010004。[实际加载器字节](evidence/dsp-file-loader-2026-10-12.json)、[离线执行结果](evidence/dsp-address-map-2026-10-12.json)。无设备I/O、DSP执行或固件写入。

**CoMi实际ARM加载器使用的MCU地址与固定Leopard参考SDK不同。录音DSP首段目标DSP `0`映射为MCU `01140000`，第二段目标DSP `40000000`映射为MCU `01040000`。** 参考SDK常量不能直接用于本机固件或RAM读写。

## 两段实际目标

DSP地址按16-bit字寻址；section长度与文件读取长度按字节计。实际section头来自[录音DSP首段提取证据](evidence/record-dsp-first-section-2026-10-12.json)，下表地址转换已通过原始ARM指令离线执行验证，正文未在模拟器加载或执行。

| code section | DSP起点 | 正文字节数 | 实际MCU起点 | 根据长度计算的MCU结束位置，不含 |
|---|---:|---:|---:|---:|
| 第一段 | `00000000` | 5312 / `14c0` | `01140000` | `011414c0` |
| 第二段 | `40000000` | 8944 / `22f0` | `01040000` | `010422f0` |

结束位置是区间计算；不表示对应物理RAM容量已实测。后续[主code链读回](record-dsp-export.md)已取得第二段完整正文，并发现第三段DSP起点`40006000`、长度1288 B；表中两个地址转换的模拟边界不变。

## 实际与参考来源

实际映射内联于`1003c96e..1003ca30`；[固定SDK soc_dsp.h](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_dsp.h#L39-L132)用于解释地址类型，不能替代实际常量。

| 区域/条件 | CoMi实际加载器MCU基址与DSP起点范围 | 固定Leopard SDK常量 |
|---|---|---|
| code低地址/PTCM | `01140000 + 2*dsp`，`0000..1fff` | CPU基址`30058000` |
| data低地址/DTCM | `01100000 + 2*dsp`，`0000..bfff` | CPU基址`2ff30000` |
| ROM code | `ff000000`，`10000..1ffff`，不累加DSP偏移 | 同一ROM基址与DSP范围 |
| EXT，code/data | `01040000 + 2*(dsp-40000000)`，`40000000..40017fff` | CPU基址`2ffe0000`；DSP上界`4003bfff` |
| SHARE，code/data | `01068000 + 2*(dsp-40044000)`，`40044000..40047fff` | CPU基址`2ff18000`；DSP基址`40100000` |
| 其余地址bank回退 | `inner=dsp & 4003ffff`；仅`1000..cfff`映射`01040000 + 2*inner` | inner起点`35000`，范围与本机不同 |

表中PTCM/DTCM/EXT/SHARE名称来自参考SDK与指令结构对应，物理命名未通过芯片手册验证。流程有优先级：如code `2000..bfff`不会按DTCM加载，会进入bank回退；不要把低地址code范围上界误当全函数拒绝边界。实际EXT/SHARE映射还存在重叠MCU区间；不能据此推断可同时独占使用。

## MMIO与边界

实际`1003c9a8..1003c9c6`计算无符号`destination-01040000 <= 00017ffe`；匹配时读取`400010c0`并清除mask `01500000`，随后调用文件读取。按SDK相似流程推断与DSP RAM访问权/时钟来源切换有关；**具体寄存器含义与物理所有权效果未实测**。

离线执行验证：第二段目的地`01040000`触发该读改写；第一段`01140000`不触发；code DSP `bfff`映射`01057ffe`仍触发；data DSP `c000`通过bank回退映射`01058000`，已不触发。合成初值`a5ff5a5a`变为`a4af5a5a`，仅用于验证位操作。

`1003c9d2..1003c9de`在读取后对同一条件设置mask `01500000`。此恢复操作仅静态确认；模拟器成功用例在`1003c9ce`的payload read调用前停止，避免将外部文件读取桩、后续指令或真实硬件行为混为一谈。

**加载器只转换section起点，不按size检查终点。** 用code DSP `1fff`、size `4000`的合成section，实际指令仍准备向MCU `01143ffe`读取`4000`字节；这会跨越低地址PTCM映射的起点范围上界。它证明该函数缺少段末检查，不能证明此输入在设备上安全。EXT起点`40017fff`接受、`40018000`拒绝，返回`fffffff2`（−14）。

## 复现与限制

```sh
uv run tools/verify_dsp_address.py artifacts/mapped-system/mapped-system.bin
```

SHA绑定已验证的927632 B ARM映像，执行原始section loader；仅seek/read/tell/log入口改成`BX LR`桩并拦截参数。9个用例使用手工固定的地址、边界和位运算结果作为oracle；每例500指令上限，未知外部执行/内存访问立即失败。接受路径在payload read调用前停止；拒绝路径执行至返回。

未复制或执行DSP机器码，未验证寄存器真实语义、RAM容量、bank切换、DSP启动、完整文件或整机恢复。下一步可用这些实际映射检查完整DSP各段的目标与重叠，但刷机依据仍需独立恢复入口与官方镜像。
