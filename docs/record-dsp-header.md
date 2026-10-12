# 录音 DSP 完整头部：实机双读

2026-10-12。读取 `aerecord.dsp` 所在 `0x24d400` 与 `0x24d600` 两个512 B块；完整540 B头的每一行均至少两次一致，无冲突。没有执行DSP代码、修改flash或进入升级模式。

依据：[实际SDFS目录](nor-partition-prefixes.md)、[实际540 B加载器](dsp-file-loader.md)、[完整捕获与头部JSON](evidence/record-dsp-header-2026-10-12/header.json)。头部SHA256：`aae650f37a8158e8f89d73af89df062863ce2dfde2276621511c7d8546e2b4b6`。

| 项目 | 文件内偏移/值 |
|---|---|
| 文件长度，目录声明 | 110148 B |
| magic / entry | `xhqy` / `0x8e` |
| 工具 / 算法版本word | `0x01030000` / `0x01000000` |
| 主code / data段表 | 540 / 16112 |
| bank18 code / data | 52812 / 0 |
| bank19 code / data | 52968 / 0 |
| bank34 code / data | 80636 / 105520 |
| 其余61组bank | code、data均0 |

全部非零指针都在头部之后，且文件内至少剩8 B供段头读取。第二块还实测首个code段头：size5312 B，DSP目标地址0；仅取得该段的部分内容，不能据段头宣称段完整或运行有效。

## 采集与可靠性

- `first/`：22次producer，32行全见，仅31行双覆盖。`0x110`某次落在窗口首端，缺少完整前置CRLF；严格解析丢弃，未生成sector。
- `second/`：新连接22次producer，32/32行双覆盖，补齐第一块；两轮合并无冲突。
- `end/`：第二块22次producer，32/32行双覆盖，22.583 s；其前28 B补齐540 B头。
- `failed-cold-window4.json`：一次单窗口补读失败；实际F0文本在RAM行的第11个字节后直接接命令echo，剩余dump丢失。64 ACK和F1齐全仍不构成有效读回。保留原始通知，不把失败数据用于头部。

因此21.8 s/512 B是此前boot样本的单次测量，并非无重试吞吐保证。内容、异步日志及环形位置均会影响覆盖；导出必须保留失败、检查逐行双覆盖，不能按已发送命令数累计备份长度。

## 离线重建与检查

```sh
uv run python - <<'PY'
import json
from pathlib import Path
from rcominote.nor_windows import analyze
root = Path('docs/evidence/record-dsp-header-2026-10-12')
first = analyze(sorted((root / 'second').glob('window-*.json')))
end = analyze(sorted((root / 'end').glob('window-*.json')))
raw = bytes.fromhex(first['sector_hex']) + bytes.fromhex(end['sector_hex'])[:28]
with Path('artifacts/record-dsp-header.bin').open('xb') as output:
    output.write(raw)
PY
uv run comi diag inspect-dsp-header artifacts/record-dsp-header.bin 110148
```

解析器要求恰好540 B、正确魔数和每个非零指针的8 B边界。文件长度来自目录，不能拿头部自身替代；检查不涉及段内容、DSP地址映射、文件checksum、boot验签或恢复能力。

下一步：从已确认范围提取完整110148 B资源，并按section链和SDFS checksum验收。仍无整机原始备份或可验证恢复路径。
