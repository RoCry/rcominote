# 交接

2026-10-15。替代此前的 `archive/ubuntu-handoff.md` 和会话外的临时交接文件。

## 一分钟了解

- 设备、分区、SDK 现状见 `README.md` 和 `device-platform-map.md`。
- 计划只有一份：`roadmap.md`。当前卡在 M1，等用户拆机。
- BLE 逐页备份路线已停止，代码在 `src/rcominote/experiments/`，报告在 `docs/archive/`，不再推进、不再审计。
- 工作规则见 `AGENTS.md`。之前的 receipt / checkpoint / frozen snapshot / 双 agent 互审机制全部废止。

## 私有材料（不在 Git）

Ubuntu 主机 `/home/rocry/w/_hw/rcominote/artifacts/`：原始抓包、SDK 包、APK、工厂区 raw、录音样本。约 4.7 GB。其中 `factory-rw-*`、`prefilled-factory-*` 含设备工厂配置，不公开、不写入文档。

## 已知未解

- 实体 SoC 丝印、PCB 版本、NOR 封装、SWD 焊盘位置：拆机后一次解决。
- 磁吸线有没有 USB 数据脚：拆机看走线。
- boot 是否验签：`boot-security-source-audit.md` 只分析了 SDK 源码；本机 ROM 行为未知，M4 时才需要回答。
- BLE 日志通道固定丢第二帧前 244 B（Linux/Android/macOS 一致，固件侧 HCI ring 问题）：不再研究，物理路线不依赖它。
