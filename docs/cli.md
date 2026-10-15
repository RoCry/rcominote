# CoMi uv CLI

安装依赖与入口：

```sh
uv sync --all-extras
uv run comi --help
```

Python≥3.13；依赖与工具版本固定在 `uv.lock`。正式包 `src/rcominote/`，在仓库根目录运行 `uv run comi`，由uv管理项目环境。不依赖 rlcdv 或旧 `tools/comi.py`。

设备命令默认按广告序列号选择自有 C261CF0430；Boyi 操作连接后再次核对 GET_SERIAL。其他自有设备通过各命令 `--serial SERIAL` 选择。诊断 code profile 仅支持当前有证据的设备/入口，不能移植到其他设备盲读。

## 发现与状态

```sh
uv run comi doctor             # 离线环境与能力边界；不扫描
uv run comi capabilities
uv run comi scan --seconds 8   # 被动扫描
uv run comi info --out artifacts/info.json
uv run comi gatt --out artifacts/gatt.json
uv run comi recording-info
uv run comi settings show
```

设备模式以当前固件及用户屏幕对照为准：`mode=note`对应原始01，`mode=call`对应02；未知模式拒绝解析。文件/START/STOP的`kind`另用Note01/Call00，不能套用模式枚举。旧CLI曾将模式01误标CALL；历史仅有该标签的记录不能证明物理CALL。CLI没有已确认的模式setter，按说明书手动切换。见[模式与音频验收](note-call-audio-2026-10-13.md)。

结果是 JSON；错误非零退出，通常向 stderr 输出 JSON 错误；带操作观测的取消或删除未验证会保留 stdout JSON。证据文件拒绝覆盖。macOS 的宿主终端需有蓝牙权限；官方 App 先断开。Linux 设备访问依赖本机 BlueZ/适配器/权限；SSH 不会把 Mac 的 USB/BLE 自动转发过去。`doctor`不把“依赖已安装”说成“蓝牙权限已通过”。

Linux普通Boyi命令用显式LE/public ATT连接，避免BlueZ5.72自动选BR/EDR；要求扫描得到public地址、设备靠近本机适配器。本机验收无须sudo、配对或修改BlueZ服务。[实机验收](evidence/linux-boyi-cli-2026-10-13.json)覆盖info/files、已有240522 B录音完整导出与12s watch；录音/设置/实时流/物理Ctrl-C尚未在Linux实测。`gatt`与Actions诊断仍为独立通道，当前日志缺片限制见[Ubuntu交接](archive/ubuntu-handoff.md)。

## 录音与导出

```sh
uv run comi record start
uv run comi record pause
uv run comi record resume
uv run comi record stop
uv run comi files
uv run comi download NAME_FROM_FILES --out artifacts/recordings
uv run comi download NAME_FROM_FILES --offset 17 --out artifacts/recording-ranges
uv run comi sync --out artifacts/recordings
uv run comi set-time
```

录音操作检查起始状态、响应格式及操作后的实际状态；不接受错误状态上的重复操作。`set-time`使用主机本地时间，现有协议没有已知时钟getter，因此只报告匹配响应和请求时间，不宣称读回成功。

下载要求声明长度、完整字节、结束帧，且和文件列表长度一致；超量、短读、断连、错误状态或无声明立即失败。临时`.part`成功后以不覆盖方式原子发布，输出SHA-256。普通失败清理临时文件。

目前音频下载使用BLE；未建立可用的USB下载路径，不代表硬件只能通过BLE传输。`download`和`sync`在交互终端的stderr显示每个文件的百分比、已收／总字节、速度及ETA；非终端stderr不显示进度，stdout保持JSON。进度按实际写入字节计算；`--offset`仅统计请求的剩余范围。达到100%后仍需通过结束帧、长度及本地发布检查，显示`Saved`才是完成。最终JSON附`transfer_seconds`和`average_bytes_per_second`：从发起文件传输至返回的耗时及平均有效载荷速度，不含扫描、连接、文件列表和最终fsync；取消结果的耗时包含有界停止等待。实时速度与ETA是估算，首包前可能没有数值。

`download`或`sync`传输中按一次Ctrl-C：已收到数据时发送一次`STOP_GET_FILE=0x0c`，最多等待1秒停止回复，然后关闭连接；首包前取消只关闭连接，避免固件启动线程清除停止标志。已写入内容保存为`NAME.offset-N.RANDOM.partial.bin`，附`.partial.json`，记录offset、字节数、SHA-256、完整文件声明长度及停止尝试结果；不是完整MP3，不自动续传。没有数据则不生成空文件。输出取消JSON，退出码130；`sync`保留之前完成的结果，并结束批次。磁盘保存失败仍报错；再次Ctrl-C强制中断不保证文件保存。

请求尝试写入GATT后，若超时、取消、协议解析或下载写入失败，该连接不再接受后续请求；保留本次原始错误，后续操作要求新建连接。协议没有事务编号／下载文件ID，清空队列无法隔离迟到响应。参数预检失败、等待事务锁时取消、完整接收后的本地fsync失败不使连接失效。重连只隔离主机接收队列，**不证明设备下载线程已经退出**；超时或磁盘错误不会自动发送停止命令，未提供可靠续传保证。[取消协议依据与实测](download-cancel-contract.md)。

`sync`跳过已存在同大小的普通文件，明确标注 `verification=size_only`，不能当成和设备内容哈希一致。大小不同或符号链接拒绝覆盖；选择新目录自行核对。设备未提供文件hash，CLI hash只标识本次收到的字节。

录音测试产生的原文件不会自动删除。显式单文件删除：

```sh
uv run comi delete NAME --serial SERIAL --confirm-delete NAME
```

必填实际serial并重复文件名确认，连接后再次读回serial；要求设备idle、完整文件列表包含目标。只发送一次`0x0d`，保留回复原始字节，再取完整列表核对目标消失。成功JSON的`scope=listed_recording_absence`只表示目标不再列出，不证明安全擦除或其他副作用。超时、断连、列表不完整为结果未知；收到回复但仍列出为未满足后置条件，均退出1、不重试。尝试删除后Ctrl-C报告结果未知并退出130。**已用本轮新建、双下载留存的测试录音实机验收**；新连接列表恢复原7项，现有录音未作为删除目标。见[来源、实测与边界](file-deletion.md)。

## 管理请求：效果未验证

固定官方App其余请求已集中到`maintenance`；只按明确选择发送，不自动登录、重试或重连。所有操作必填实际serial，读回核对身份，要求idle。

| 命令（省略共同的`--serial SERIAL`） | 含义及完成边界 |
|---|---|
| `maintenance bind USER_ID --confirm bind` | ID为1..16可打印ASCII字节，补零、不截断；等待匹配回复，不证明云账号身份或持久绑定 |
| `maintenance unbind --confirm unbind` | 默认保留录音；只写一次后关闭失效连接，不把断连当完成 |
| `maintenance format --confirm format` | 等待匹配回复，不能证明格式化完成或安全擦除；可能丢失设备数据 |
| `maintenance factory-reset --confirm factory-reset` | 恢复出厂请求，不是普通重启；只写一次后关闭失效连接，不证明复位完成或ROM退出能力 |
| `maintenance phone-type android`（或`ios`） | 显式发送0或1，没有已知getter；不按主机OS自动设置 |

解绑时若明确要求删除录音，还必须同时传`--delete-recordings --confirm-delete-all SERIAL`；单独传任一项均拒绝。绑定不允许删除标志。Phone type的iOS1是主机限制，不代表固件只接受0/1。

输出`scope=request_submission_only`：匹配回复或write-only写入完成后仍为`status=submitted_unverified, ok=false, device_effect_verified=false`，**退出3**，表示提交未验证；不是效果成功。错误／超时／断连不确定为`status=unknown`退出1，尝试后取消为unknown退出130；没有效果成功0。`request_sent=null`表示失败前是否完成写入无法确认，不能解释成未发送。CLI保留回复和错误，关闭连接；关闭失败也按unknown报告。Bind/phone等待5秒、format10秒；write-only的5秒是主机上限，非官方固件时序保证。**尚未实机执行任何这些管理操作**。[来源、全部请求覆盖与独立golden](remaining-client-contracts.md)。

## 实时音频

```sh
# 被动采集；不开始或停止设备录音
uv run comi realtime --duration 10 --out artifacts/live.bin
# 显式创建短录音，采集后停止；设备必须先处于 idle
uv run comi realtime --record --duration 5 --out artifacts/live-test.bin
```

最长300秒、最多16 MiB，输出拒绝覆盖；失败不发布成功文件。
原样保存 e5e3 通知拼接字节，JSON 报告字节数、包数、hash及录音身份。
`.bin`表示指定时间窗口的实时数据，不保证完整录音。物理确认的NOTE/CALL各6s样本均为MP3/16kHz/mono/32kbps，实时拼接与各自完整下载逐字节一致；这不证明物理麦克风接线、声学差异或长时无丢包。需要完整文件时按报告中的录音名另行 `download` 对照。
被动采集可能得到零字节；不会因此自行启动录音。

`--record`尝试清理自己启动的录音；START等请求失败导致连接失效时，无法再用同一连接确认或停止。错误会明确提示录音可能仍在运行，需重连查看状态并按需停止；不把清理尝试当成停止成功。
2026-10-13听筒NOTE测试实际遇到此序列：断连后新连接仍读到recording，显式STOP恢复idle，离线文件完整导出；实时采集仍记失败。[现场记录](note-call-audio-2026-10-13.md#电话听筒call--note-与一次断连恢复)。

连接期间保留e5e3订阅，结束采集只移除本地接收处理，再断开连接。
原因及实测见[共享CCC状态](realtime-ccc-gating.md)、[实时MP3比对](realtime-live.md)。

## 离线 OTA 包检查

```sh
uv run comi inspect-ota /path/to/ota.bin
# 仓库自带的合成格式样本；不是CoMi固件
uv run comi inspect-ota tests/fixtures/ota-sdk-golden.bin
```

不扫描、不连接设备、不解包或烧录。检查AOTA头部、完整数据和各文件CRC，
以及目录数量、名称、文件范围和重叠。输出XML中的板名／版本作为元数据；
不把“容器完整”当作“本机接受”“签名有效”或“可以恢复”。
检查器增加了设备解析器中未见的目录／文件边界校验，见[实际容器检查](ota-container-contract.md)。
`application_gates.known_rejections`额外报告FW010004的三个已知拒绝条件：缺少`ota.xml`、
清单长度≥2048、未以`<?xml`开头。自带SDK样本CRC通过，但会明确报告缺少XML声明。
拒绝列表为空仍不证明设备接受；清单语义、板名匹配、payload目标及恢复尚未验收。
退出码0只表示离线容器检查成功，不表示这些设备检查通过。
加密或整体压缩的外层文件不自动猜测、解密或展开。

## 设置

```sh
uv run comi settings set noise 8        # 0..16
uv run comi settings set usb on         # on/off
uv run comi settings set indicator off
uv run comi settings set voice off
uv run comi settings set backlight on
uv run comi settings set segment 1h     # 30m/1h/2h/3h
```

所有setter均显式选择；已有值相同就返回 `already_matches`，不重复发送。设备报告null时拒绝setter。设置后的 `GET_DEVICE_INFO` 必须等于请求值，收到ACK本身不算成功。失败不会自动猜测/追加其他命令。

当前实机确认noise、backlight、segment可写并读回。[2026-10-13往返验收](evidence/settings-roundtrip-2026-10-13.json)：backlight关→开→关，segment3h→1h→3h；每次新连接info原始字段吻合，结束原值恢复、7项录音不变。USB setter未实测，indicator/voice仍报告null。未观察屏幕物理效果、长时自动分段或重启保持；segment四档是App标签，不是已证明的固件边界。精确协议依据见[能力规格](cli-capabilities.md)。

## 日志、固定诊断与代码样本

```sh
uv run comi diag probe --out artifacts/prepare.json
uv run comi diag capture version --out artifacts/version.json
uv run comi diag capture platform --out artifacts/platform.json
uv run comi diag capture commands --out artifacts/commands.json
uv run comi diag capture kernel --out artifacts/kernel.json
uv run comi diag capture stacks --out artifacts/stacks.json
uv run comi diag capture code --out artifacts/code1.json
uv run comi diag capture code --out artifacts/code2.json
uv run comi diag compare-code artifacts/code1.json artifacts/code2.json --out artifacts/analysis.json
uv run comi diag text artifacts/platform.json
```

其他profile：`logs` 默认实时日志、`threads` 详细线程表、`nor-header` NOR头读取尝试。`threads`已观察到设备端长输出截断；`nor-header`已知没有数据正文，不是备份工具。所有日志会话限1–30秒、默认5秒，结束发送STOP并等待结束帧；`transport_ok`表示传输完整，**不代表命令成功或正文完整**。固定代码读取另校验每个请求的数据行；缺行、短行、重复行均使`ok=false`并非零退出。

`code-literals`在核对入口指令后读取其两个常量（8 B）；`code-references`进一步读取固定引用，总计69 B、五个非连续位置。两次采集可用`diag compare-references FIRST SECOND --out REPORT`离线比较。[证据与推导](code-reference-followup.md)。

`vendor-code`核对本次会话的`vendor`与`vendor_read`入口，读取固定380 B：两个入口、后者至已证实常量池前的连续代码及六个常量。常量/后续代码读取前还要求入口字节精确吻合。两次采集用`diag compare-references FIRST SECOND --vendor --out REPORT`比较；连续Thumb代码合并后解码，避免16 B传输行拆断32位指令。[实机代码分析](vendor-code-readback.md)。

`vendor-handler`读取固定580 B，含32 B已有调用链校验、实际命令分发表和`0x3a`处理函数/引用。逐层核对入口、BL、表尾和literal；每四行刷出并等待正文，失败停止后续读取。两份捕获用`diag compare-references FIRST SECOND --handler --out REPORT`比较，输出58项分发表，明确将TBB表与literal排除出代码。[分发表及未知边界](vendor-dispatch-followup.md)。不发送`0x3a`或其他新增应用命令。`platform`增加固定只读`BT_NAME`查询，与`BT_LE_NAME`分别报告。

code只读固定映射地址的16 B，并在同会话核对当前logsrv入口；不接受任意地址、长度或shell文本。离线比较拒绝重复采集身份（包括复制同一文件），要求两次样本一致，返回解码与hash，不执行机器码。此能力不等于完整flash dump、板级适配或可恢复备份。

## 一键只读验收

```sh
uv run comi verify --code --out artifacts/verification-NEW
```

新建独立目录，依次保存身份/状态、GATT、平台诊断、可选两份code与离线比较、结束状态和manifest。要求开始idle；不会开启录音、改设置、重启或刷写。失败仍保留已取得的证据并非零退出。code可选且限定FW1.0.4。

USB主机描述符：`uv run comi usb snapshot --out artifacts/usb.json`（macOS）；`uv run comi usb diff BEFORE AFTER`离线比较。`snapshot`不会打开设备端点。

## 开发与独立分发

```sh
just check       # 格式/lint/脚本语法、离线真实帧和故障序列测试
uv build         # wheel + source distribution
```

参考板SDK构建仍是独立研究工具，仅Linux x86_64。准备脚本默认下载固定SDK和工具链；构建脚本显式接受`--sdk`、`--toolchain`、`--out`、`--jobs`：

```sh
bash tools/setup_sdk.sh
uv run --locked tools/build_sdk.py \
  --sdk "$HOME/w/_tmp/lv_port_actions_technology" \
  --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" \
  --out artifacts/sdk-build --jobs 4
```

APK固定样本提取仍用`uv run tools/apk_evidence.py ...`。这些研究脚本不参与设备CLI运行；`justfile`仅保留每日检查入口。

旧研究记录中的 `tools/comi.py`、`tools/log_capture.py` 等路径与命令对应当时提交；截至c523137可按原命令复现。当前统一使用以上入口；旧脚本已迁入包，不保留两份实现。

`device-info-code`沿已验证的命令05调用链读取601 B（112 B既有校验点），含52 B设备信息构造、常量和两个容量getter。读取前逐层验证指令、literal、callee入口；两份捕获用`diag compare-references FIRST SECOND --info --out REPORT`离线核对。[字段来源](device-info-fields.md)。没有新增写入或固件备份命令。

`storage-code`扩展device-info-code至937 B，沿实际容量getter、卷名表、RAM挂载对象及函数表定位statvfs callback。`diag compare-references FIRST SECOND --storage --out REPORT`逐字节核对两份捕获。新增336 B含40 B RAM元数据；当前指针/flags/代码不吻合即停止，不自动跟随新地址。RAM并非原子快照，重启后固定地址可能失效。[存储绑定证据](storage-binding-readback.md)。

`disk-code`在storage-code上增加550 B（共1487 B），跟随FatFs、磁盘registry与实际指针，到`sd`后端和`MMC_1`设备对象；没有调用init/read/write/ioctl。用`diag compare-references FIRST SECOND --disk --out REPORT`离线核对并输出`disk_metadata`，复算缓存簇容量，拒绝未知free-cluster缓存。[证据与限制](disk-registry-readback.md)。新增RAM地址每次由当前父指针核对；值变化即停止，不能作为通用dump。

`card-code`沿disk-code新增544 B，共2031 B固定SD/MMC驱动代码与状态引用；离线输出`card_metadata`；逐层核对当前指针和调用指令，不调用init/read/write/ioctl、不访问MMIO。两份采集用以下命令比较；[实机驱动状态与边界](card-state-readback.md)。

```sh
uv run comi diag capture card-code --out artifacts/card-first.json
uv run comi diag capture card-code --out artifacts/card-second.json
uv run comi diag compare-references artifacts/card-first.json artifacts/card-second.json \
  --card --out artifacts/card-analysis.json
```

`boot-code`继承card-code校验，沿实际device_get_binding→31项device表→Flash实例/回调读取2931 B；其中字符串区有重叠。`diag compare-references FIRST SECOND --boot --out REPORT`输出`device_names`、`flash_configuration`；32 MiB是配置容量，不是芯片容量实测，也不是完整固件备份。[证据](boot-storage-device-readback.md)。裸`just`仅列命令；`just check`才执行检查。

`nor-code`继承boot-code，沿实际NOR read目标、地址模式helper读取缓存ID/flags；固定3101 B读取、3068不同字节。`diag compare-references FIRST SECOND --nor --out REPORT`输出`nor_state`；不发送JEDEC命令或调用Flash函数。[ID与容量边界](nor-driver-readback.md)。

`printk-state`：核对owned设备、完整固定镜像头及三段实际代码/literal后，读取console device、init/panic、字符hook共10 B。逐次flush和验收，不执行fread或跟随返回指针。`diag inspect-printk CAPTURE`离线重新校验并解释保存状态。[两次实测与边界](printk-runtime-state.md)。
