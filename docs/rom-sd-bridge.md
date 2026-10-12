# 已知 ROM → SD → Boyi：两次独立实测

2026-10-13，C261CF0430 / FW010004。**ROM `1900..1a50`（末端不含）336 B可经原厂 `dumpbuf` 写SD，再经现有下载器导出。两次下载均与此前独立双读的字节完全一致。**
这解决“该已知ROM源能否走文件通道”，不解决ROM总范围、完整备份、RAM执行或恢复。

## 方法与结果

沿用[已审计的SD桥合同](sd-file-bridge.md)：固定系统头、完整dumpbuf代码/literal在线守卫；新增ROM首尾各16 B守卫，任何不符先停止。源地址/长度固定，不开放任意ROM探测。
每次选择不同随机名称，检查可见文件名碰撞；生成文件、结束日志会话、按名称下载后逐字比较独立oracle。

| 下载 | SD名称 | 字节 | 下载时间 | 全流程时间 |
|---|---|---|---|---|
| 首次 | `rc6c7aab595e` | 336 | 0.182 s | 9.661 s |
| 重读 | `rc5413d06407` | 336 | 0.184 s | 7.083 s |

SHA256均为 `0dda0a4532813627df78b506bfa1f7e5dc8ae4b9886cc32173265592defcaa67`，与[原独立ROM oracle](evidence/rom-flow-2026-10-13.bin)一致。
两会话各17 ACK、F1结束、无残留半帧；原始帧离线重解码并复验全部守卫。前后均为自有设备、FW010004、idle。
[两份下载、删去个人录音列表的报告与分析](evidence/rom-sd-bridge-2026-10-13/analysis.json)已入库；诊断帧未改动。

## 固定实验入口

在仓库根目录，先解压已入库system gzip至本地文件，再运行：

```sh
uv run -m rcominote.experiments.sd_bridge artifacts/mapped-system/mapped-system.bin artifacts/rom-sd-new --source rom-flow --create-sd-file
```

需要现有蓝牙访问权限、精确匹配的system镜像和未存在的输出目录。命令会留下一个336 B非音频SD文件；每次完整重跑都会新增一个，不能当只读操作。
本轮保留 `/SD:/RECORDER/Call-rc6c7aab595e.mp3`、`Call-rc5413d06407.mp3`；未尝试删除。

## 路线影响与停止条件

- 已知ROM区间可绕过逐行mdb导出；未来若取得可信ROM边界/可读映射，可考虑一次有界语料采集后离线分析。
- 本次336 B不能推导整个ROM可读、DMA访问范围或批量吞吐；不根据常见芯片大小直接扩到32 KiB。
- 直接XIP→SD全零原因继续停放；没有新证据重开驱动调试。
- 未进入ROM模式、上传/执行程序、写NOR或验证复原。ROM枚举仍需独立退出方式；[正常接口盘点](normal-ram-entry-inventory.md)也未找到受支持的RAM执行合同。

下一阶段优先匹配BSP/SDK与明确加载/恢复材料；不围绕这336 B逐个callee新增工具。
