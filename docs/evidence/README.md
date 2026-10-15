# 证据索引

更新至2026-10-14。当前工具已迁入uv包，旧脚本路径对应各轮历史提交；现用命令见[CLI](../cli.md)。历史说明、源码事实和本轮实测分开；历史文本中的绝对路径只用于追溯，不是运行依赖。

本页是证据历史，不是待办清单；执行优先级只看[当前路线](../research-routes.md)。

[较大binary NOR出口有界收据](nor-binary-export-boundary-2026-10-14.json)、[具名入口与边界](../nor-binary-export-boundary-2026-10-14.md)：20段实际bytes/3固定SDK文件复验通过；`snort`完整路径含64KiB erase和512B pattern write，不可作为读取实验。已审fread/dumpbuf/Boyi/driver/recovery入口仍无安全较大raw出口；结论不覆盖未审路径，无设备操作。
Wi-Fi的实际固件、App与精确型号证据由[专题汇总](../wifi-capability-2026-10-13.md)串联。

[常驻导出命令静态收据](resident-export-command-inventory-2026-10-14.json)、[具名入口与副作用](../resident-export-command-inventory-2026-10-14.md)：28段actualbytes/3固定来源复验，固定coredump4096B常驻读缓冲/文本输出及RAM恢复链闭合；无可选任意NOR地址/长度，该已审路径未建立安全通用binary出口，未实测该命令。

[冻结覆盖库存](nor-backup-coverage-2026-10-14.json)、[来源层级与缺口](../nor-backup-coverage-2026-10-14.md)仍ASOF24200 A36112/B155204/available191316B；后续10页5120B加privatefactory6144B只作索引overlay，当前强来源**47376B**、可用潜在**202580B**。System连续raw首6144B`[24000,25800)`完整，剩余system raw未完整备份；B来源不完整不升级，factory累计6144B完整pair、余2048B缺完整覆盖，DSPextra444B缺raw，禁止mapped/reencoded/FF填补。冻结库存/旧收据不改。

## 下载窗口参数控制与7.5ms/CE1策略，2026-10-14

[activity next4b失败/accepted-prefix收据](prefilled-factory-activity-next4b-live-2026-10-15.json)、[冻结原whole拒绝与首512独立审计](../prefilled-factory-activity-next4b-live-2026-10-15.md)：仅page0-1ed600成功pair新增512，两RAMoracle+NORstrict4096/512相等/fullsource-state-HCI；page1-1ed800 LEconnect成功后21ATT58HCI discovery timeout/reason08，零identity/download/Actions/SD，后两页零I/O。总283ATT510HCI40977B/15complete/0pending/status；原whole/page1false、parentgate拒绝。最新actualpage0second4096/identity18:57:20.885464UTC14/free59589，失败后独立无HCI info不能补after或验证SD；all90plannednonce reserved/cohortmax72另计。aa5a153source140tests293继承2786+159/351formatlint/build/357inputs/new_full_check_run=false；新helper review非正式CP/plan/live。全factory/carrier/sectorhash/hex/nonces私有，无binary；覆盖47376/202580/factory6144missing2048/system6144。旧4a/ONE及失败receipts不改，不自动retry。

[activity next4a四页成功收据](prefilled-factory-activity-next4a-live-2026-10-15.json)、[全冻结chain/pairs与private首段格式复验](../prefilled-factory-activity-next4a-live-2026-10-15.md)：新2048私有raw`[1ece00,1ed600)`，4actualFAST/no pulse，1053ATT1811HCI155077B/60complete/0pending/1boundstatus(page2ATT96)/4normal16。20DL8RAM8NOR16samefile覆盖0newfiles/NORwrites；8RAMoracle+8strict4096/4equal512pairs/parentstate完整通过，current4096/history82/identity18:52:05.581566UTC14=02:52:05HKT15/free59589。plain+oldcomposer各4，DEFAULT integrated/wake新form未radio；aa5a153source140tests继承2786+159/351formatbuild/357inputs/new_full_check_run=false。首段八actualpair sectors共4096/12recordsCRC+namehash/padding/empty416/actualtail3680FF，无fill/新coverage/full8K或restoreclaim。全factory/carrier/sectorhash/hex/nonces私有，无binary；覆盖46864/202068/factory5632missing2560/system6144/cohortmax72；旧ONE及失败receipts不改，后续另fixedplan。

[activity单1ecc00成功收据](prefilled-factory-activity-one-live-2026-10-15.json)、[冻结全chain/pair复验](../prefilled-factory-activity-one-live-2026-10-15.md)：新512私有raw，两RAM4096独立oracle+两NORstrictprefix4096/512相等；freshbaseline==defaultCPf870 ownedobject，当前4096/parentgate通过。261ATT451HCI38700B/15complete/0pending/status/normal16，actualFAST/no pulse；gap plain/composer-before-crlf，DEFAULT集成和新增wake form未radio实测。5DL/2RAM/2NOR/4samefileSD覆盖/0newfiles/NORwrites，非0storagewrite；finalidentity18:44:21.057460UTC14=02:44:21HKT15/free59589/NOTEidle/unboundcharging100。history74与cohortmax72不同；CP f8700deviceI/O/coverage、原notice/NEXT3失败保持。aa5a153source140tests/fresh2786+159/56.73s351formatbuild/357inputs一致；全factory/carrier/sectorhash/hex/nonces私有，无binary。当前覆盖44816/200020/factory3584missing4608/system6144；后续另fixedplan，不自动retry/扩展。host吞吐理想81.16h/4MiB非ETA或新binary出口。

[notice单1ecc00失败收据](prefilled-factory-notice-one-live-2026-10-15.json)、[冻结startup拒绝/全wire复验](../prefilled-factory-notice-one-live-2026-10-15.md)：legacyFAST-only拒绝实际完整DEFAULT24..40/0/500→36，wakegap-v3未达到；0completed/下载/Actions/RAMexport/NORproducer/SDwrite/newfiles/coverage。61ATT123HCI5123B/1complete/0pending/status/normal16，setup→before→inventory→after全消费，finalidentity18:13:06.952796UTC14=02:13:06HKT15/free59589/NOTEidle/unboundcharging100。formalhostCP5eb2采纳原NEXT3 observedSD4096/state/history70、0deviceI/Ocoverage、原9comm/旧gap失败复现；不假定residentring不变，本轮未baseline reread。two plannedunsent→futureReserved72，与cohortmax72不同；CP ASOF70/所有旧失败保持。dd58冻结151source138tests/fresh2745+159/48.62s347formatbuild/353inputs一致。全factory/carrier/sectorhash/hex/nonces私有，无binary；覆盖44304/199508/factory3072missing5120/system6144不变；新live/计划/扩展停止，下一步仅host DEFAULT→actualFAST beforebaseline，不重连碰FAST/补判。

[BOOT0 direct F0失败收据](actions-fread-boot0-live-2026-10-15.json)、[冻结原错误与rawHCI独立诊断](../actions-fread-boot0-live-2026-10-15.md)：DEFAULT36→FAST12→host6CE1/1，update113在marker115/fread119前；host64ATT/raw66ATT TX27相同/RX37为39前缀，差仅STOPACK/F1。原wholefalse/32rows错误/session-retired after_error/RX mismatch保留，无finalidentity；raw143HCI6143B/7ACK/2FULLF0text533/terminalF1/0pending/0canonicalNORrows/2fillers/normal16。非旧244B缺片，不推断NOR硬件读取失败；不补尾/比较payload/发布binary。后续独立无HCI CLI info59589/NOTEidle/unbound/charging100，观察上界17:52:24.863939UTC14，不替代原after。64e7冻结150source136tests/fresh2704+159/344formatbuild/350inputs一致；conditionalimage29regions DMA/raw先于BLEcallback，livepointer/init未知，不把MDB ring读当稳定被动snapshot。0SD/write/coverage/history70；ownedfile未复核/未admitted/最后NEXT3failedfirst，覆盖44304/199508/factory3072missing5120/system6144不变；stream/frame/marker/factoryhash私有。

[Actions applied6 RAM256成功收据](actions-fast-ram256-live-2026-10-15.json)、[冻结全stream/关键byteRX复验](../actions-fast-ram256-live-2026-10-15.md)：STARTACK+settledFAST后host6CEhints1/1真实生效再afc/MDB；4FULLF0/5ACK/terminalF1/0pending，16连续RAMrows256匹配独立oracle、每byteRX在commandTX后，0fillers。72ATT144HCI/2complete/0status/normal16，17:32:49.553447UTC14=01:32:49HKT15 identity59589/NOTEidlecharging100。0SDaccess/write/rawcoverage/新files；historicalONE仅IDENTITYONLY/current_owned_file_verifiedFalse，最后ownedSD仍NEXT3failedfirst未复核/未admitted/history70，不能当旧ONE current。e5aa149source135tests/fresh2675+159/342formatbuild/348inputs一致；fullstreamhash/hex/afc/factorycarrier私有，无binary。oldloss45/45/60ms不同于newap6，单control非causalrepair/可靠性/NOR路线；覆盖44304/199508/factory3072missing5120/system6144不变。

[factory NEXT3失败脱敏收据](prefilled-factory-next3-failed-2026-10-15.json)、[接受512与原53B OSgap拒绝](../prefilled-factory-next3-failed-2026-10-15.md)：仅1eca00完整pair新增512；1ecc00 first完整4096/SLOW/barrier/identity后原three-gap grammar拒绝`Ble wake lock 0` notice，无sector/oracle/newpolicy/覆盖；该页后2stage及1ece00零I/O。437ATT761HCI/24txn0pending/status/8DL6覆写0newfiles/2normal16；finalidentity17:09:26.871464UTC14=01:09:26HKT15，pageend29.041263/wholeend29.041613。当时failedfirstprivate4096不同于旧ONE，state59589已观察但whole/parentgate拒绝/无新CP；后续RAM-only linkcontrol成功不复核/采纳SDfile；70reserved含3unsent。32c147source133tests继承2634+159/338formatbuild/344原inputs/new_full_check_run=false；当前hostcode另行实现。所有factory/carrier/sectorhash/hex/nonces私有，无binary；强44304/潜在199508/factory3072missing5120/system6144/cohortmax72；不自动retry。

[fresh单1ec800成功脱敏收据](prefilled-factory-one-live-2026-10-15.json)、[全冻结重放与linkCP边界](../prefilled-factory-one-live-2026-10-15.md)：新baseline全4096实读匹配hostCP639e采纳旧thirdsecond，fresh身份确认后两NOR各独立RAM4096预填充/strictprefix4096/两512相等，新增512私有raw。266ATT456HCI/15txn/0pending/1boundstatus atATT230/normal16，5DL4覆写0newfiles；两gapPLAIN，新CRLFcomposer未radio。finalidentity17:01:10.006458UTC14=01:01:10HKT15，pageend12.176809/wholeend12.184642；当时currentprivate4096/state59589/history64/wholeparentgate通过，后被NEXT3failedfirst覆盖。CPunknown-only/0I/Ocoverage/原failed4保持，old42identity/44pageend/52failureend分离；32c147source133tests/fresh2634+159/338format/build/344inputs一致。Factorysector/carrierhash/hex/nonces不公开/无binary；强43792/潜在198996/factory2560missing5632/system6144/cohortmax72，后续另固定计划。

[RAM预填充factory四页失败脱敏收据](prefilled-factory-four-live-2026-10-15.json)、[三完整pair/第四GATT timeout边界](../prefilled-factory-four-live-2026-10-15.md)：1ec200/400/600各完整pair新增1536私有raw/全六NORstrictprefix4096/六RAMoracle通过；第四LE已连但21ATT仅MTU/discovery，reason08/errno110，零identity/CCC/application/download/SD/NOR/coverage。全808ATT1415HCI/45txn/15DL12覆写/0status/newfiles，3normal16+1timeout08；原wholefalse/parentgate拒绝。当时最后身份16:40:42.033534UTC14=00:40:42HKT15，thirdpageend44.229530；wholeend52.894850无新身份。当时expected第三secondprivate4096/last59589、无postfailure新读回/CP；后续正式unknown-onlyCP639e仅ownership/0I/Ocoverage，freshone新实读确认后成功，原whole仍false；62reserved含第四2unsent，cohortmax72。ab99冻结146source132tests/fresh2610+159/336format/build/342inputs一致；所有factorybytes/sector/carrierhash/hex/nonces私有，无binary。强43280/潜在198484/factorytotal2048missing6144/system6144；no retry。

[RAM预填充known-v2成功收据](prefilled-known-v2-live-2026-10-15.json)、[全冻结重放/方法边界](../prefilled-known-v2-live-2026-10-15.md)：两次全4096RAMoracle预填充后，known0/4200均strictprefix4096/criticalchain无exemption/独立sectororacle通过；dualprevious角色分离。266ATT/456HCI/15txn/0pending/**1boundstatus atATT97**/normal16，5DL/4覆写/0newfiles/0coverage。实际两gap都是PLAIN，新composer分支仅hosttested；当时16:11:31UTC14=00:11:31HKT15 privatecurrent4096/state59589/history54/wholeparentgate已验，后续factory部分失败见上方，所有carrier/baselinehash仍私有/无新binary。actualCP3a35仅采纳原v1通信/0I/Ocoverage/原failed保持；cf72冻结145source129tests/继承2547+159/331format/build/337inputs一致。强41744/潜在196948/system6144/factory余7680/cohortmax72不变；后续未知范围另固定计划。

[RAM预填充known失败脱敏收据](prefilled-known-failed-2026-10-14.json)、[冻结重放/精确原separator失败](../prefilled-known-failed-2026-10-14.md)：baseline全4096匹配实际factoryCONTENTCP36db，RAMprefill4096独立oracle通过；firstNOR0完整下载/SLOW/barrier/finalafter后原54B分隔语法拒绝，无sector/oracle比较。后两stage零I/O，175ATT/310HCI/9txn/3DL/2覆写/0newfiles/0coverage/normal16；当时11:52:36Z当前private4096/真实59589/52reserved已观察，wholefailed/parentgate拒绝。factorybaseline和新currentcarrierhash均私有，SDprefill不清residentring。9139冻结144source127tests/继承2445+159/328format/build，334inputs一致；CP只通信/ownership0I/Ocoverage/原factory失败保留。强41744/潜在196948/system6144/factory余7680/cohortmax72不变；随后actualCP3a35仅通信/ownership0I/Ocoverage；新freshv2控制另成功，原v1仍failed。

[privatefactory四页失败脱敏收据](factory-first4-failed-2026-10-14.json)、[全冻结source重放与隐私边界](../factory-first4-failed-2026-10-14.md)：首`[1ec000,1ec200)`完整pair新增512私有raw；1ec200first单份0coverage，secondfull4096/barrier/finalafter后原v3prefix4095拒绝，physical4095col41未变`f`为变量lowhex，常量formatter-mask不能证明。后两页零I/O，无raw/config/contenthash/publicbinary；364ATT/636HCI/18txn/0pending/status/2normal16，6DL/4覆写/0newfiles/cohortmax72。当时11:16:39Z privatecurrent4096/真实59589/NOTEidlecharging100已观察，wholefailed/parentgate拒绝、50reserved；后续factoryCP36db仅采纳通信/ownership/0I/Ocoverage，原failed不改。实际Stage1 STATUSCP4467仅采纳旧STATUS4通信/ownership/0I/Ocoverage；9af140source/122tests/继承2301+159/319format/build/new_full_check_run=false。强41744/潜在196948/factory余7680未完整，system6144保持；精确用户controls“只有电源键和录音滑键”，独立退出仍未证。 [RAM预填充known0/4200对照](../verified-prefill-control-plan-2026-10-14.md)计划原v1现已实测失败，结果见[最新脱敏收据](../prefilled-known-failed-2026-10-14.md)；不补判此前变量尾部。

[STATUS4known失败收据](status-known-failed-2026-10-14.json)、[实际offlineCP与原9comm重放](../status-known-failed-2026-10-14.md)：g0baseline/first完整，second4096/barrier/finalafter全过但原STATUS4prefix4095拒绝，physical4095未变space/row25col42separator仍strict；无secondsector/新maskparse/secondoraclecodeccompare/新binary/coverage，g0candidatefalse/g1零I/O。182ATT/319HCI/9complete/0pending/status/normal16；当时10:50:08Z ring`02c4d169642728323622c3369455be5d7b71a448eb6898cfb6394fcf9976a6c4`，现被factoryprivate对象替代/真实59589/NOTEidle/charging100已观察、wholejob/parentgate拒绝，42reserved，3DL/2覆写/0newfiles/cohortmax72。545c140source/122tests/preIO2294+159/319format/lint/build；actualofflineCONTENTcheckpoint53f8采纳原v3failure9comm/current8714/history38/0I/Ocoverage，旧failed不翻案。后续actualStage1CP0coverage+factory失败见上方，变量byte不能靠常量mask证明；该轮当时41232/196436/system6144不变。

[continuous known15失败收据](continuous-known-failed-2026-10-14.json)、[原9事务communication与v3拒绝重放](../continuous-known-failed-2026-10-14.md)：g0baseline/first完整、second4096/真实barrier后原prefix4095拒绝，physical4095ASCII0/status`buf=0x`非v3row-space豁免；无secondsector/新policyparse/secondoraclecodeccompare/新publicbinary/coverage。181ATT/317HCI/9complete/0pending/status/normal16，g0candidatefalse/g1两producer零I/O，无额外baseline。当时10:20:56Z ring`87146b6b9e18eca8af8c09e3fcfe074260386d38ebed08aefbab91c98b34d364`，现被STATUS4second替代/真实59589/NOTEidle/charging100已观察，wholejob/parentgate拒绝；34+4=38reserved、非admittedhistory。3DL/2同文件覆盖/0newfiles/cohortmax72，de1e139source/119tests/preIO2216+159/314format/lint/build冻结。旧bulk/首4K/41232/196436不变；后续actualofflineCONTENTcheckpoint采纳通信/0coverage、新STATUS4仍失败见上方；完整formattermask尚无live。

[25000四页v3成功收据](paired-nor25000-four-live-2026-10-14.json)、[全链复验](../paired-nor25000-four-live-2026-10-14.md)、[actual新raw2048](paired-nor25000-four-live-2026-10-14/nor25000-25800.bin)：4完整pair新增`[25000,25800)`2048/SHA5cc9…91edb，727ATT/1269HCI/36complete/0pending/status/4normal16。25200second prefix3827/其余7份4096/关键链内/无豁免，8次6ACKF1/F0各0，composerF,T,F,T,F,F,F,T。当时10:17:24Z ring`f6781e2966e47b548c6b2f0f5ccd2c48d19b97cd172c1d1b4dd7d7b08a28c2a8`，现被上方failed15second替代/真实free59589/NOTEidle/charging100/history34；4连接/12DL/8覆写/0新files/cohortmax72。未修改W0隔离副本139+117/3055执行，继承2137+159/build/new_full_check_run=false；后验fixed32各512匹配mapped、非raworacle/key。旧首4K/失败/W0收据不改，强41232/潜在196436，system连续首6144；后续continuous15已失败见上方，旧成功不受影响；下一窄formatter proof/checkpoint仅review。

[独立只读owned-file恢复收据](owned-file-recovery-live-2026-10-14.json)、[全链复验](../owned-file-recovery-live-2026-10-14.md)：成功完整4096下载/真实finalidentity，当时10:07:03Z ring`a5d8e2e773a38954f35d8b2f919fa585e09df0a13c7a9c29a6ac6da4a76f5a48`，现已被上方bulk替代/NOTEidle/unbound/charging100/free59589，90ATT/168HCI/3complete/0pending/status/normal16，0Actions/producer/SD写/新文件/NOR覆盖。current不同于旧f0b5，未NORparse/oracle；旧known控制仍false/group0candidate不升级。parent admission通过/26history，139source/117tests/3055/preIO2137+159/build冻结，额外postIOtests不混入；后续控制source实现中无新live结果。W0当时首4K/39184/194388/cohortmax72不变，无新publicbinary；后来bulk新增见上方。

[known同连接控制失败收据](two-known-session-failed-2026-10-14.json)、[失败时对象未知与复验](../two-known-session-failed-2026-10-14.md)：group0两boot0候选完整/oracle匹配，group1 baseline完整匹配前second；第三次覆盖有6ACK/F1/F0=0，但无新FAST/host归一/下载，inner8s超时，second未开始。222ATT/377HCI/11complete/0pending/status、normal16；wholefalse/candidate不升级/0新coverage/files。最后09:40:32.022126Z f0b5…ffd3/free59589在第三次尝试前；09:40:43Z当时结束后**文件未知、设备状态未验证**（后续新W0只读观察见上方），未finalidentity，不能继续称a16e或f0b5为current。92e2冻结138source/116tests/2107+159/build，原件全wire/真实barrier重放；无新raw。随后独立只读checkpoint已成功见上方，旧失败不补判；该失败当时原首4K和39184/194388覆盖不变，后续bulk叠加见上方，cohortmax72未变。

[system首4KiB原始收据](system-first4k-raw-live-2026-10-14.json)、[8页来源与完整复验](../system-first4k-raw-live-2026-10-14.md)、[actual raw4096](system-first4k-raw-live-2026-10-14/system-first4k-raw.bin)：新24c/e两个pair全过新增1024B，18txn/364ATT/634HCI、全4prefix4096/noexemptions/F0各0、composer[T,T,F,T]/实际身份/两normal16通过。旧24000原44窗口及其他7pair全source重放，8实际512顺序拼接SHA74807d16…7d83a5c，非原子/fullsystem/4MiB/restore证明；旧failedjob/24a候选不补判。当时09:10:35Z ownedring a16e83146f8957a06240a781df08f476cdcfd8dd76d6843aa26ce60eb6a14609/free59589，现已历史化，当前新W0只读观察见上方，新4overwrite/0新files/cohort仍70+1+1=max72。d546冻结138source/114tests继承2062+159/build、此次未新跑fullcheck；该capture用原冻结source，后续known同连接控制实际失败见上方；后续只读checkpoint已成功、下一控制代码另行实现，不当原capture语义或已验。

[新v3固定24a00成功收据](paired-nor24a00-v3-live-2026-10-14.json)、[完整重放与prefix界限](../paired-nor24a00-v3-live-2026-10-14.md)：[actual512](paired-nor24a00-v3-live-2026-10-14/nor24a00.bin)两freshproducer结果相等SHA6234e0aa…4ebdb9f、新增512B；first4095仅physical4095/row30/col2已知地址space豁免，second3872/noexemptions/allcritical已在内，不能声称whole4096write。offlinecheckpoint0coverage/0设备I/O，原四页failed及旧24a候选不补判。180ATT/316HCI/9txn/0pending/status/F0、normaldisconnect16/实际身份全过；当时08:48:38Z ownedring6249…2258a/free59589，现被上方新pair覆盖，新2覆盖0新files/cohort仍70+1+1=max72。138source/114tests冻结/2062+159/build；后验fixed32匹配预声明mapped512，非raworacle。随后24c/e按新固定计划完成首4KiB，见上方；原收据不改。

[固定四页失败收据](paired-nor-system4-live-2026-10-14.json)、[完整原prefix与失败边界](../paired-nor-system4-live-2026-10-14.md)：planned2048B，仅24600/24800各完整双读通过，[actual24600](paired-nor-system4-live-2026-10-14/nor24600.bin)/[actual24800](paired-nor-system4-live-2026-10-14/nor24800.bin)共新增1024B。24a00 first完整4096/6ACKF1F0=0/6txn/真实barrier，但原strictprefix4095拒绝、无512候选输出/零覆盖；不证actualshortwrite，second零命令、24c00零I/O，wholejobfalse保持。该批501ATT/881HCI/24complete/0pending/status0，3normaldisconnect16；当时07:53:40Z/ownedring4c5e92d9…dd4ae96/free59589，现已被上方freshv3覆盖。3连接/8下载/5同文件覆盖/0新文件，cohort70+1+1=max72。原137source/112tests沿用v2冻结2021+159/build；后续v3/checkpoint及新24a成功见上方，旧失败不改判。

[首个genericv2单24400收据](paired-nor24400-live-2026-10-14.json)、[全原件重放](../paired-nor24400-live-2026-10-14.md)：182ATT/318HCI/9txn、两6ACKF1/F0=0、两完整4096及全HCI/identity/normaldisconnect16后，两[actualraw512](paired-nor24400-live-2026-10-14/nor24400.bin)相等SHAd3a2b556…797ce2e，新增`[24400,24600)`512B。2同文件覆盖/0新文件；当时ring513cf…49ab/free59589，现已被后续任务覆盖。固定32reset后验512/512匹配预声明mapped，非raworacle。137source/112tests/2021+159/build记录冻结，不能当当前开发source通过声明。

[未知系统24200双读收据](system24200-live-2026-10-14.json)、[真机验收与后验解码](../system24200-live-2026-10-14.md)：同一owned文件两freshnonce/producer/覆盖、三完整4096下载，180ATT/316HCI/九完整事务/0pending/0status、两prefix4096与最终状态/normaldisconnect16全过。[actual raw512](system24200-live-2026-10-14/system24200.bin)两份逐字相等SHAf9337ab9…cc3227e，新增`[24200,24400)`，无独立oracle；后验固定32reset解码512/512匹配mapped向量页，预期未参与raw验收。134source+108tests/1953+159/build，root/Astra归档重放通过；当时59589保持、当时ring96a615…9ef9c，现已被后续任务覆盖，零新文件/cohort仍max72。旧失败保持；整片备份/恢复/自写固件未完成。

[scratch已知4200单覆盖成功收据](scratch-4200-live-2026-10-14.json)、[真机方法与界限](../scratch-4200-live-2026-10-14.md)：baseline完整匹配postmortem当前boot0文件，freshnonce/一次同路径覆写/完整下载后512B匹配独立raw4200 oracle；136ATT/243HCI/6txn/0pending/0status、6ACK/F1/F0=0、prefix4096与producer-gap exactcomposer全过。新ring10bd351c…33e1，零新文件/已分别观察两不同known内容；旧F0失败不补判、0uniqueNOR增量、不推整片效率/恢复。131source+104tests/1886+159/build；latest59589/normaldisconnect16，cohort70+1+1=max72。

[scratch只读postmortem成功收据](scratch-postmortem-live-2026-10-14.json)、[原文件保留内容新观察](../scratch-postmortem-live-2026-10-14.md)：单连接/4096B新hash3621a69c…60360、89ATT/167HCI/3txn/正常disconnect；零Actions/producer/SD写。原nonce→status/32rows跨wrap/producer/dump/prefix4096全部过，boot0匹配独立oracle，确认上一同路径覆盖后内容已更新；原F0失败不翻案，未完成两target/无新增NOR覆盖。128source+101tests/1833+159/build；latest59589不变/cohort仍70+1+1=max72，fullring/HCI私有。

[scratch首次复用失败收据](scratch-reuse-live-2026-10-14.json)、[实测与只读接续](../scratch-reuse-live-2026-10-14.md)：原baseline完整4096/hash一致、first真实6ACK/F1/pending0/F0=0，一次producer/同路径SD覆盖已尝试；在覆盖后下载前停止，second零I/O、整体保持失败。125source+98tests/1766+159/build；107ATT/192HCI/3txn/normaldisconnect16，最终59589身份未变，0新files。更新内容未确认，不能将旧device对象继续当原baseline，也不推断uptime未执行。

[最后2e00与完整boot1收据](final-boot-sector-live-2026-10-14.json)、[真机验收与边界](../final-boot-sector-live-2026-10-14.md)：新独立pair真实FAST、148ATT/255HCI/六完整参数/0pending/0status、两个freshproducer及完整4096环全验。旧3584来源重放后保存[actual boot1全4096B](final-boot-sector-live-2026-10-14/fw1_boot.bin)与[最后sector](final-boot-sector-live-2026-10-14/sector2e00.bin)，实际全FF，无有效备用boot代码；未知块无独立oracle、非完整4MiB备份/恢复。120source/1641+159/build；latest59589，70confirmed+1declared+1possible=max72，原失败保持。

[受控三地址任务收据](startup-boot-tail-live-2026-10-14.json)、[两pair成功与最后特性交换失败](../startup-boot-tail-live-2026-10-14.md)：actual2a/2c各完整双读、freshness/6txn/barrier/HCI全通过；各自[sector2a](startup-boot-tail-live-2026-10-14/sector2a00.bin)、[sector2c](startup-boot-tail-live-2026-10-14/sector2c00.bin)来源独立，不以相同FFhash替代。新增1024→前3584/4096B；两NOR实际startupFAST、0status，不声称NORDEFAULT实测。2e零ATT/identity/Actions/SD，23HCI特性交换status3e→errno38，原job失败无fullbin；119源码/1627+159/build及全部旧来源/control重放通过。latest2c59590，cohort68+1declared+1possible=max70。

[Linux LE特性错误映射收据](linux-le-features-error-2026-10-14.json)、[本机模块与原始HCI闭环](../linux-le-features-error-2026-10-14.md)：本机bluetooth.ko实际指令及v6.14 primary源码证明status3e→defaultENOSYS38；23rec原件/feature event/零ATT逐项核对。未运行模块/设备程序，不推断RF原因或称ATT不支持，不改判原失败。

[DEFAULT已知RAM真机成功收据](startup-ram-default-live-2026-10-14.json)、[两连接控制与适用边界](../startup-ram-default-live-2026-10-14.md)：seed真实FAST12/normaldisconnect后，新连接DEFAULT36，两个3ACK/F1日志pulse后均真实FAST→host6/0/500→4096B独立oracle→EOF SLOW/身份barrier；46+137ATT、107+251HCI、1+7完整事务/0pending，两次normaldisconnect。实际F0/status均0；排序不唯一归因trigger，所有旧失败保持。118源码归档重放通过，1605+159/build；latest59590、零SD/新scratch/NOR增量，覆盖仍前2560/4096B。

[默认参数与日志pulse静态收据](ble-default-parameter-path-2026-10-14.json)、[路径及对照门槛](../ble-default-parameter-path-2026-10-14.md)：30段actual bytes固定hash，100ba772默认24..40/0/500、FAST no-op清pending bit9、delayed worker默认分支及日志活动可安排FAST。3ACK/F1 pulse无shell/文件/NOR路径，但改临时日志RAM/timer，PREPARE标志至disconnect清；仍需完整F0解析/真实FAST/因果索引，不由静态宣称pulse已成功。

[同scratch复用静态收据](nor-scratch-reuse-static-2026-10-14.json)、[新nonce与覆盖试验计划](../nor-scratch-reuse-plan.md)：36段actual bytes核uptime额外argv/原echo、dumpbuf0x12从cursor0同长覆盖及Boyi重新open。只允许既有owned专用4096对象，覆盖前完整hash、两个fresh只读nonce、已知boot0→4200oracle；此静态收据不证明live；后续复用实测与原失败分别见上方，不增加该静态收据的NOR覆盖或声称无SD写。

[剩余三地址任务启动参数收据](status-remaining-live-2026-10-14.json)、[完整default事务与零执行失败](../status-remaining-live-2026-10-14.md)：首2a00完成61ATT/GATT/身份/列表后，remote24..40/0/500→applied36与固定FAST门槛不同，主动拒绝，1complete/0pending。final身份HCI111..119在update110后，严格等于before/expected/health/free59590。零Actions/producer/SD写/新增覆盖，后三剩余范围仍未知，原job失败无fullbin。113源码冻结，1516+159/build及旧2560prefix来源全重放通过；不改判历史失败。

[新四地址任务收据](status-boot-tail-live-2026-10-14.json)、[新2800成功与2a00 GATT超时](../status-boot-tail-live-2026-10-14.md)：新2800完整双读新增512B→前2560/4096B，[actual安全chunk](status-boot-tail-live-2026-10-14/sector2800.bin)独立来源已验。255HCI/148ATT/六参数/零pending；显式状态策略启用但实际0事件。2a00已建立连接，19ATT发现中监督超时，无producer/SD写；后两未执行、原job失败无fullbin。110源码冻结，旧前缀与state链原版本全重放；两新scratch下载确认。随后只读health恢复正常，不改判旧失败。

[只读GATT/身份健康收据](status-link-health-2026-10-14.json)、[当前通信复验](../status-link-health-2026-10-14.md)：46ATT逐包绑定107HCI/4201B，完整GATT、前后身份严格等于新2800.after/free59590，单次远端FAST完整结算。关闭后2.023812s捕获disconnect0x16，位于最终ATT之后。零Actions/SD写/状态事件，无新增覆盖；当前通信恢复不证明先前超时根因或修复。

[五扇区窗口任务收据](window-boot-tail-live-2026-10-14.json)、[2600成功与2800事件边界](../window-boot-tail-live-2026-10-14.md)：2600完整独立双读通过，[actual512安全chunk](window-boot-tail-live-2026-10-14/sector2600.bin)新增512B→fw1_boot前2048/4096B。2800两份完整候选及六参数/barriers保留，但额外状态0F使原finalaudit拒绝，原pair/job失败，后三未执行、无fullbin。107件原源码快照，旧prefix22窗口原始来源全重放；latest实际state59590，Ubuntu62已下载scratch+1旧声明+1可能。后续事件策略与状态checkpoint不改判该失败。

[限定composer语法的新2400双读成功收据](window-nor2400-composer-2026-10-14.json)、[完整复验与边界](../window-nor2400-composer-2026-10-14.md)：两次新producer/nonce、完整4096B、六事务全结算、严格freshness/second previous-dump锚及真实身份/state通过。149 ATT/256 HCI、零pending，second实际接受33B精确显示计数行（有静态来源，非任意日志忽略）。[512B原始安全chunk](window-nor2400-composer-2026-10-14/sector.bin)来自新first，双读相等、无独立字节oracle，新增512B→fw1_boot前1536/4096B；其余五扇区未知。34件新源码快照；Ubuntu58已下载scratch+1旧声明+1可能。原失败收据不改判。

[新窗口策略2400双读失败收据](window-nor2400-live-2026-10-14.json)、[日志新鲜度边界](../window-nor2400-live-2026-10-14.md)：两份4096B下载完整，first严格512B/slow/identity barrier通过；second producer→dump间精确composer异步行导致拒绝，second slow尚待Update、无第二barrier，pair原失败。141 ATT/245 HCI及34件源码快照保留；final状态通过不替代fullaudit；新增raw覆盖0，Ubuntu56份已下载scratch+1旧声明+1可能。

[按下载窗口控制参数的收据](download-window-live-2026-10-14.json)、[真机时序与适用边界](../download-window-live-2026-10-14.md)：同一既有RAM文件连续两次完整4096B匹配独立oracle；115 ATT逐字节绑定205 HCI记录，五次参数事务完整结算。两次host归一6/0/500均在实际GET_FILE前完成；EOF slow请求可早于End，但更新均在完整End后生效；每次再通过真实identity/state barrier。18件private源码快照；零新增SD文件、零新增raw覆盖。原tail失败保持，下一步适配有界NOR双读，不推断worker退出/隐藏缓存清空。

[固定备份boot tail失败收据](backup-boot-tail-2026-10-14.json)、[真机结果与参数边界](../backup-boot-tail-2026-10-14.md)：固定六地址任务只执行2400，第一份完整通过，第二GET_FILE已声明4096但offline0B，额外更新请求使pair/job失败；后五无producer。14件源码快照、first checkpoint及完整191-record HCI保留。新增双读覆盖0，无完整分区输出；旧1024B配对覆盖保持。独立后续health free59591不替代失败after；不重跑相同early计划。

[未知0x2200双读收据](dual-unknown2200-2026-10-14.json)、[严格新鲜度、失败诊断与early成功](../dual-unknown2200-2026-10-14.md)：首轮失败原件保留；新early6/0/500 trial两次独立producer/文件/4096环、148 ATT/HCI及真实barrier全通过，两份512B全FF相等，新增pair-verified覆盖512B，无独立字节oracle。[原始安全chunk](dual-unknown2200-2026-10-14/sector.bin)来自新成功首读，不挪用旧2000样本。`fw1_boot`已覆盖前1024/4096B；53份scratch下载确认、另1可能，未删除。完整原始报告/抓包/源码快照私有，公开metadata不替代全父链replay。

[单连接连续导出收据](dual-known-nor-live-2026-10-14.json)、[真机原型与完整replay](../dual-known-nor-live-2026-10-14.md)：一连接boot0→4200，各5ACK/F1、完整4096下载及512独立oracle；224 HCI记录与150 ATT包双方向逐字节绑定，一次参数更新/真实identity barrier通过。两个独立checkpoint保留，完整最终replay通过；已知目标不增加历史raw覆盖。该阶段Ubuntu系列50份测试文件下载已确认、另一次可能残留。

[完整RAM4096下载收据](sd-interval-live-2026-10-14.json)、[边界与复验](../sd-interval-live-2026-10-14.md)：实际HCI一次更新至interval6/latency0/timeout500、CE hints1/1，下载4096B逐字节匹配独立系统初始化oracle，前后状态相同。基线45ms；不能称纯interval单变量或历史15ms受控比较。原认证stdinEOF失败发生于设备I/O之前，仍保留；新目录b为首次实际试验。完整HCI/report私有，公开必要参数事件及hash。

[新ring基线与boot0收据](sd-nor-interval-live-2026-10-14.json)、[原始NOR闭环与边界](../sd-nor-interval-live-2026-10-14.md)：fresh context28、完整ring基线4096及boot0结果4096分别通过；原始512B匹配旧独立oracle。首次context发现超时零写仍失败，独立context-b通过。新增三份SD测试文件，累计45；无NOR写/ROM进入，不是整片备份或恢复证明。

[非零offset4200双读收据](sd-nor-offset4200-live-2026-10-14.json)、[重复性及监控早收尾](../sd-nor-offset4200-live-2026-10-14.md)：两个新producer/文件/连接，完整512B分别匹配既有raw recovery oracle；public安全片段4194B、private33源全链复验。两capture112/113记录均正常SIGINT sent/exit0，无cleanup disconnect记录仍据实保留；完整下载区间门槛通过。新增两SD文件，累计47；已知sector交叉验证不增加旧raw覆盖。

[boot1 block1单读状态收据](backup-boot-block1-2026-10-14.json)、[早期重连失败的边界](../backup-boot-block1-2026-10-14.md)：当时2200单读512B全FF完整通过；第二份连接失败零写，没有pair-verified新增覆盖。原首次下载连接失败也保留。三个原报告hash固定；新增一份文件下载已确认，另一次SD写尝试可能留文件，该阶段Ubuntu系列48份已确认、最多49。原方法停止；后续early成功独立记录于上方。

## Actions官方测试盒/板级/DUT材料，2026-10-13

[官方U2引脚/网络复验](actions-official-u2-pin-links-2026-10-15.json)、[有界符号恢复与适用边界](../actions-official-u2-pin-links-2026-10-15.md)：固定PADS源/目录与KiCad schema/mapper恢复ATS3085C_SOCKET全部69个声明引脚及69个typedwire端点，345pin切片及4结构切片hex/SHA独立复核。WIO1=31/WIO0=34、UART0TX/GPIO28=49/RX/GPIO29=50、USBDM=51/DP=52仅官方参考原理图符号/网络事实；不证明CoMi芯片/焊盘/PCB铜连接/磁吸线/独立RESET或ROM退出，无设备/厂商程序执行。

[下载收据/原始成员](actions-official-acquisition-2026-10-13.json)固定三个7z、两个FW、SCH/PCB/BOM及说明页；[包结构](actions-official-packages-2026-10-13.json)记录ACTTEST0而非Q、tester八成员CRC全通过、DUT另一头布局/一项零CRC未验、type100和108个FAT输出（7个原始编码块）。[SDK/helper/recovery对照](actions-official-lineage-2026-10-13.json)保留指令/54文件基线；[硬件证据](actions-official-hardware-2026-10-13.json)包含精确BOM单元格和PADS类型记录/原始字节，并注明BOM修订不一致。复现工具和适用边界见[官方材料报告](../actions-official-tester-2026-10-13.md)；没有设备操作或厂商程序执行。

## maker内层与随包宿主，2026-10-13

[封装/native读取证据](maker-package-static-2026-10-13.json)核对legacy/type100、独立CompoundFW格式及FAT/XOR分支；DB转换未实现。[样例恢复清单](maker-sample-2026-10-13.json)绑定固定SDK源hash与43项恢复文件hash，31项宿主名称/长度匹配SQLite表；2 MiB/11项布局、空芯片/USB配置及与既有LARK helper逐字节相同，排除把样例作为CoMi恢复包。工具和复现见[生产包专题](../production-package-contract.md#随包样例43个文件已恢复但不是comi恢复包)。全离线，无vendor代码或设备执行。
[宿主选择/31 B包头](host-maker-selection-2026-10-13.json)与[18段原始字节](host-maker-regions-2026-10-13.json)核对USBDevice→指定DLL→family0/CClassical、13上传/20切换及函数内未校验状态；port为既有transport对象，没有CoMi选择链。两份host DLL可从固定RAR/CAB重复恢复，三模块Ghidra全新项目复验通过。[结论](../host-selection-followup.md#2026-10-13-recovered-maker-host-conditional-default-now-identified)。

## Android第三主机与完整HCI，2026-10-13

[原始逐包收据及源哈希](android-log-hci-loss-2026-10-13.json)：无root bugreport
在完整HCI启用后取得515846 B raw snoop；原disabled摘要只有command/event、0ACL。
最小安卓工具已实机完成身份/状态查询；一次help仍缺第二512 B帧首244 B，
全部11条Actions通知与Linux HCI逐字节相同，手机HCI与全部应用回调/特征写一致。
STOP独立尝试并保留原始ACK/F1，整体仍失败；独立结束info完整payload等于初始、NOTE/idle。
[方法、复验及决策](../android-runtime-followup.md)。原始bugreport/手机记录留ignored目录。
[实际异步TX调用链](android-tx-path-2026-10-13.json)已将入队成功、异步发送、共享HCI
ring失败及队列释放绑定同一CoMi镜像；20窗口和dispatch表可离线复验。它证明实际
候选机制，未证明捕获时执行了该失败分支，不能宣布缺片根因。

## 国内第三方源码续查，2026-10-13

[实际获取与查询收据](domestic-sdk-renewed-2026-10-13.json)：新Gitee Actions Android宿主源码两仓库固定版本/选定文件哈希已核对；CSDN开发者原文给出旧LARK `SDK-TAG_ZS308A_2700_220112`、板型及具名固件。同系列221215仓库为空；已下载SDK30F手册属于2004年Z80/ATJ208X。记录原生搜索、公开Git、索引/登录/验证码边界；未取得匹配M4 BSP或CoMi恢复包。[内容与价值](../domestic-sdk-followup-2026-10-13.md#renewed-domestic-pass-source-acquired-exact-older-lark-package-identified)。

## Linux普通CLI，2026-10-13

[直接LE/Boyi验收](linux-boyi-cli-2026-10-13.json)：已绕开BlueZ5.72错误BR/EDR选择，状态、12项列表成功；已有240522 B文件导出4.2746s，SHA256匹配此前Mac独立基线，完整MP3解码通过。12s空闲watch成功；前后新连接完整info/列表相同，无录音/设置/删除/固件操作。保留单文件及平台验收范围，不能代替Actions日志可靠性、整片NOR或恢复证明。

## Linux短输出对照，2026-10-13

[固定16 B读取失败收据](linux-short-read-2026-10-13.json)：第6次版本查询触发日志，首512 B帧仅488 B后出现完整55 B新帧；HCI/socket全部14通知一致，含STOP尾部。目标行在不完整帧中，不计成功。无录音/MMIO/固件写入，短输出路线未解决可靠性，停止同条件重试。

## NOTE/CALL增益与失败读回，2026-10-13

[47段固定镜像字节及SDK合同](note-call-runtime-static-2026-10-13.json)：
闭合选定BLE START异步路由；132项增益表全部匹配LARK源码，365/405分别请求
36.5/40.5 dB、ADC字段不同。[两次诊断失败与原始通知](note-call-runtime-attempt-2026-10-13.json)：
新工具guard与旧工具Actions-only对照均帧错误；未启动录音、未取得运行GPIO/ADC快照。
新连接确认NOTE待机；暂停读取路线。[解释与限制](../note-call-audio-2026-10-13.md)。

[独立旧帧逐字节对照](log-fragment-loss-2026-10-13.json)：首512 B一致，第二帧缺首244 B、后268 B一致；
`uv run tools/verify_log_fragment_loss.py`可离线复验，不重建缺字节。
[SDK发送链及Ubuntu对照](log-fragment-host-control-2026-10-13.json)：可见源码未建立丢片根因，
Linux两次停于连接阶段，Mac最终NOTE/idle；不是修复或可靠传输验收。

[后续Linux HCI及位置对照](linux-le-hci-2026-10-13.json)：普通客户端实发BR/EDR并Page Timeout；
显式LE靠近PC后成功到达ATT，旧gatttool拒绝设备MTU请求。新诊断首试缺CID bind导致EINVAL；
修正随后已真机完成LE/双向MTU/发现；[日志HCI对照](linux-log-hci-loss-2026-10-13.json)确认缺片已在HCI边界之前。[Ubuntu接手和验收](../ubuntu-handoff.md)。完整HCI含周边设备，保留ignored目录。

## USB配置往返与主机枚举，2026-10-13

[脱敏实机摘要](usb-settings-live-2026-10-13.json)：USB_COPY on→off→on读回通过，
三次Mac清单各16节点且完全相同；最终完整info等于初始、idle，8项录音列表相同。
原配整根磁吸线接Mac，数据接线尚未验证。未重插、重启、挂载、进入ROM或写固件；
配置setter可持久化NVRAM。[研究与下一步](../usb-next-steps-2026-10-13.md)。

[随后明确的on→磁吸头断开→接回](usb-replug-live-2026-10-13.json)：本机充电
true→false→true、USB_COPY始终on、始终idle，三个完整Mac清单均同一15节点。
本次on命令走already_matches，没有发送setter；重连无传输提示或新USB节点。
无重启/ROM试验；不证明数据针脚不存在或启动门控不存在。

## 随机说明书照片，2026-10-13

[三张归档JPEG、原始HEIC与归档校验值](manual-2026-10-13/manifest.json)，
按6810→6809→6808目视核对；仅像素转码，未复制原始EXIF/GPS/设备元数据。
[产品与操作事实](../manual-2026-10-13.md)、[固件交叉核对](../manual-firmware-crosscheck-2026-10-13.md)：
模拟硅麦+骨传导麦、两个标注麦孔、NOTE/CALL与录音滑键；不证明精确安装数量、
ADC接线、USB数据或独立复位。已有测试录音本轮离线完整解码通过，无设备I/O。

## 启动参数双槽，2026-10-13

[原始各4KiB、采集归档及摘要](param-slots-2026-10-13/report.json)：16扇区各
独立双读，主槽元数据32B转换、ACPT/FVER双CRC通过且匹配旧SRAM；备用槽
完整4KiB全FF，没有有效参数副本。总8KiB关键启动产物，非完整NOR或恢复
证明。采集32次、SD临时路径64个；7个正常录音不变，结束idle。
[方法、CRC覆盖与纯离线复验](../param-slots.md)。

## Factory-RW私有备份，2026-10-13

[脱敏摘要](factory-rw-2026-10-13-summary.json)：实际ID7范围1ec000..1ee000，
完整8KiB，16块独立双读一致；第一段12条记录CRC通过，第二段全FF。
原始配置、capture和hash留本地忽略目录，未进入Git；仅合成packer oracle
纳入测试。[方法、私有离线复验和限制](../factory-rw-backup.md)。不是完整NOR或恢复证明。

## 普通设置往返验收，2026-10-13

[backlight/segment现有CLI实测](settings-roundtrip-2026-10-13.json)：4次变更，
5次独立连接info；原始byte42验证00→01→00、byte41验证03→01→03。
最终完整info及设置恢复，7项录音列表不变。仅证明字段读回，不证明屏幕
物理效果、长时分段或重启持久化；未切换USB或执行删除/复位/固件写入。

## 新建测试录音删除，2026-10-13

[实机CLI验收](delete-live-2026-10-13.json)：原7项→新增1项10256B→移除新项。
两次新连接完整导出字节一致且留本地；删除后再新连接完整列表等于原列表，
结束idle。原有录音未作为删除目标；不证明原录音字节一致、安全擦除、重启
持久性或固件恢复。音频和原录音列表不进Git。

[隐藏scratch删除静态线索](owned-scratch-delete-static-2026-10-14.json)：
固定映像中0d callee先Call-、失败才Note-；空请求仍走byte00响应构造。
精确长度拷贝后未见显式NUL存储，allocator尾部与两个前置helper效果未定。
未删除隐藏文件；不能据此绕过现有可见列表守卫。

## 首轮实测（419b628）

- [gatt-2026-10-12.json](gatt-2026-10-12.json)：`uv run tools/gatt.py --out artifacts/gatt-2026-10-12.json`，UTC 02:18:21；广告序列号选中 `C261CF0430`，连接后枚举，无应用特征读写/通知订阅。4 个服务，MTU 247，日志服务存在，普通模式 OTA 服务未出现。macOS 缓存/设备当前模式限制仍适用，不是所有模式的证明。
- `uv run tools/comi.py info`：GET_SERIAL / GET_BIND_INFO / GET_DEVICE_INFO 通过 Boyi 写请求、收通知；序列号吻合，unbound，idle，FW `010004`，total/free `59634/59632`，charging，battery 100，USB mode true。状态 payload：

  ```text
  0000e8f20000e8f00264000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000
  ```

- `usb-devices --json`：可见 Hiveton 与 Espressif 串口，未进行 probe/refresh/reset；串口清单不等于全 USB 清单，未确认 CoMi USB 接线。本轮不靠该结果推断 CoMi 芯片。
- 格式/lint/7 个离线捕获帧测试及 CLI help 见 `just check`。未构建 SDK、未刷机、未调用日志 shell；历史 HIL 不算作本轮重测。
- `tools/apk_evidence.py` 对两个固定 APK 样本均成功：1.1.2 为 1,781 个成员/11 个片段，1.2.4 为 2,165 个成员/0 个匹配片段；核对片段摘要，并验证未知哈希、已有输出目录会拒绝。完整提取文件在忽略的 `artifacts/`，复现命令见 [APK 核查](../app-upgrade.md)。

## 迁移来源

rlcdv commit [`027b547a26c624ff7b61b8e96b9327f7643671d9`](https://github.com/rocrp/rlcdv/commit/027b547a26c624ff7b61b8e96b9327f7643671d9)，`research/comi/{comi.py,protocol.py,test_comi.py}`。交接写 PR 未合并，但本轮主仓已有该提交/目录，不再依赖已消失的 worktree。

迁入 `tools/` 后，CLI 加入按广播序列号精确选设备，删去旧项目专属注释/格式整理；协议和既有 oracle 测试内容保持原样：

| 文件 | SHA-256 |
|---|---|
| `tools/protocol.py` | `ebab4ac25d787061fdbb6e46f3c67f93bdd85414fcb9991655a51c8efb99794b` |
| `tools/test_comi.py` | `d5e110b0604b9ce58b3f3fb9cec30551c4790cc3e22a12580db8dbf3763dae0c` |

## 历史快照与修正

- [handoff-2026-10-12.md](handoff-2026-10-12.md)：用户指定交接文档完整快照。
- [prior-device-research.md](prior-device-research.md)：既有设备研究笔记快照；原始抓包测试、MP3 与包装信息来源。含历史路径/旧链接，当前导航以仓库 README 为准。
- 两份历史文本的“USB 仅充电 / 已有可执行 shell / OTA 默认无签名”等表述不作为当前结论。修正见 [路线](../firmware-roadmap.md)、[SDK 核查](../actions-sdk.md)、[APK 核查](../app-upgrade.md)。

APK/SDK 由各专题文档记录样本哈希、固定版本及复现入口。原始录音、完整 APK、厂商/第三方 SDK 不纳入 Git。

## 第二轮：USB 对照与日志握手

- [USB 对照记录](../usb-log-probe.md)：用户确认数据线；connected→unplugged 无节点变化；reconnected 仅另一台 Hiveton/rcwodle 身份变化。完整原始 USB 树放忽略目录，报告保留摘要及哈希。
- [log-prepare-2026-10-12.json](log-prepare-2026-10-12.json)：一次固定 PREPARE、一次精确 ACK；本轮确实写了日志控制特征，但未发送 shell、dump、复位或存储命令。它取代“仅有 UUID”作为更强的平台证据，不证明 shell。
- 新增 USB oracle fixture来自实际 IOKit 描述符，格式/lint、共 8 个测试通过；新版工具实机运行。SDK 仍未构建，未刷写/备份原厂固件。

## 第三轮：Ubuntu 参考应用编译

- [ubuntu-build-2026-10-12.json](ubuntu-build-2026-10-12.json)：804 步干净构建、工具/依赖版本、ELF/BIN/HEX 与配置哈希、SDK 零 tracked 改动。
- [实测报告](../ubuntu-build.md)：第一次发现 freetype 写回 SDK，外部 CMake hook 修正后第二次干净构建成功；两次 BIN/HEX 哈希相同。
- 本轮没有 BLE/USB 设备操作，没有打包或刷机；GDB/完整 vendor maker 仍未验证。完整构建日志与镜像留在忽略的 artifacts 目录。

## 第四轮：实机 shell 与有界 NOR 读取尝试

- [诊断报告](../device-diagnostics.md)：默认日志、版本、帮助、NOR 头读取五次独立会话。原始通知/写入/解析文本均存入同目录 `log-{default,device-info,commands,flash-header,flash-header-flushed}-2026-10-12.json`。
- 版本正文 Zephyr 2.7.0；device 模块未找到；帮助列出 fread/snandr/reboot adfu。NOR 读取仅收到 handler 状态行，未获得512字节数据，不能当固件备份。
- 每次已收到 STOP ACK/F1；最后 Boyi 查询成功，FW/容量/idle 未变。未重启、擦写、运行恢复入口或 flash helper。
- `just check`：格式/lint/脚本语法、10 个离线测试通过，包括真实分片日志与中途断流回放。

## 第五轮：NVRAM 单键读回与 REA 归档核查

- [platform-info](log-platform-info-2026-10-12.json)：app/system 帮助、固定两个 NVRAM getter；BT_LE_NAME 返回14字节，FW_VERION失败。没有写配置；会话 STOP/F1 完整，后续 Boyi info 正常。
- [REA 1.2.4 归档摘要](rea-apk124-inventory-2026-10-12.json)：保留实际 Evidence ID/限制；完整 bundle 留 artifacts。Android provider 缺少调用者提供的 JADX MCP JAR，没有执行反编译。
- [APK 不透明文件](apk124-candidates-2026-10-12.json)：普通 ZIP 字节核查，独立于 REA；包含准确 SHA/熵/有限字面搜索范围。未发现可用原厂固件，未证明这些文件的用途。
- `just check` 格式/lint/语法及11个离线测试通过；新 oracle 对照真实 NVRAM 字节响应。

## 第六轮：线程、代码读回与远程页面入口

- [kernel帮助](log-kernel-help-2026-10-12.json)、[线程](log-threads-2026-10-12.json)、[紧凑栈表](log-stacks-2026-10-12.json)：后者25条线程+IRQ；详细线程输出在设备端截断，ACK/F1完整不代表正文完整。
- [首次16字节](log-code-sample-2026-10-12.json)、[独立重读](log-code-sample-repeat-2026-10-12.json)、[Capstone离线报告](code-sample-analysis-2026-10-12.json)：两次相同，全部解码；报告为普通离线工具结果，不冒充REA Evidence。
- 工具第二次起强制本次会话logsrv入口校验，再发送固定16字节读取；没有任意地址参数。最终Boyi info成功，FW/idle/容量未变。
- [官方产物报告](../official-acquisition-followup.md)：精确远程页面配置、GET500、服务端包澄清、本地JADX加载壳证据；未获得官方固件。
- `just check` 格式/lint/语法及12个离线测试通过；包含入口变化拒绝路径。离线代码检查实跑并验证两份真实捕获一致。

## 第七轮：统一 uv CLI 的实机与安装验收

[验收摘要](cli-validation-2026-10-12.json)：`uv run comi verify --code`完整通过；实际录音start/pause/resume/stop均读回确认；新录音56912字节，导出大小吻合，ffprobe为MP3/16000Hz/单声道/14.228秒。sync补导出3个旧文件，同大小跳过新文件1个；明确size-only。

noise设置9→8→9，每次读回吻合；最后FW1.0.4、idle、容量59634/59632、noise9。测试录音保留在设备，音频只在本地忽略目录，无删除/重启/刷机。

wheel和sdist构建成功；Ubuntu运行wheel的doctor与两份实际代码样本比较成功，证明离线安装/入口/Thumb解码，未验证Linux蓝牙设备访问。42测试+22子测试通过，含真实帧、下载短读/断连/超量、原子保存、实时入口变化、重复采集不能冒充独立读取。

当前命令见[CLI](../cli.md)，包代码`src/rcominote`；旧tools脚本已迁入，源码/捕获证据仍独立于rlcdv。

## 第八轮：沿实机指令读取常量与函数名

[首次](code-references-first-2026-10-12.json)、[独立重读](code-references-second-2026-10-12.json)、[离线分析](code-references-analysis-2026-10-12.json)：五处共69 B一致，实际读到`_logsrv_init\0`，支持公开SDK源码对应。完整推导及未知见[报告](../code-reference-followup.md)。CLI新增固定code-literals/code-references及离线比较；传输完成与读回完整分别校验，丢正文不能再报代码读取成功。

原厂公开helper新增[命令/指令证据](helper-command-map-2026-10-12.json)与[静态报告](../helper-static-followup.md)：确认rm/rs处理器和NAND首次读取的延迟初始化，未在CoMi加载或执行。[Ubuntu离线反编译](../offline-helper-analysis.md)已运行并保存可复现脚本。

后续[初始化审计](../helper-initialization-decompile.md)证明延迟初始化有可达的条件擦除/编程路径；27函数导出可复现。[OEM官方APK调查](../oem-protocol-lead.md)取得独立App产物，确认固件元数据POST与AOTA/MD5/CRC路径，但没有CoMi镜像或跨设备适配证明。固件API未调用；CoMi登录调查按用户要求暂缓。

[vendor/OTA源码审计](../vendor-service-followup.md)：排除将`vendor_read`和OTA backend `.read`误认作设备固件导出；记录通知订阅可能触发OTA状态的完整调用链。未操作这些设备服务。

## 第九轮：实机vendor接收代码

[首次](vendor-code-first-2026-10-12.json)、[重读](vendor-code-second-2026-10-12.json)、[合并解码](vendor-code-analysis-2026-10-12.json)：380 B一致，实机`vendor_read`检查D22D帧头，接收payload后调用1000b3b4；不同于公开SDK上传解析器。完整推导与限制见[报告](../vendor-code-readback.md)。未向F5F0发送命令；[App产物定界搜索](../f5f0-artifact-search.md)未找到它的handler。

## 第十轮：实机命令分发表与BT_NAME路径

[首次](vendor-handler-first-2026-10-12.json)、[重读](vendor-handler-second-2026-10-12.json)、[分析](vendor-handler-analysis-2026-10-12.json)：580 B一致，包含已有32 B校验点；新增548 B，累计997个不同映射字节。58项TBB表中24个非默认命令，23个与官方App请求编号对应；`3a`路径引用`BT_NAME`。[报告](../vendor-dispatch-followup.md)。

两项实际失败均保留：[入口短日志未刷出](vendor-handler-buffered-entry-2026-10-12.json)导致guard超时、未发送后续读取；[长突发丢失b504行](vendor-handler-lost-row-2026-10-12.json)虽ACK/结束帧完整仍失败。新profile在依赖guard前刷出短日志；每四行后刷出并等待本批完整数据，避免继续积压。最终两个会话56 ACK、正文完整。此方法不是任意长度dump性能或可靠性保证。

[配置只读查询](vendor-bt-name-query-2026-10-12.json)：`BT_NAME`与`BT_LE_NAME`均返回14 B `CoMi Note 2F01`；`FW_VERION`仍失败。没有执行`3a`或改名。最终Boyi状态FW010004、idle、容量59634/59632、noise9；未重启/刷写。

## 第十一轮：设备信息与容量来源

[首次](device-info-first-2026-10-12.json)、[重读](device-info-second-2026-10-12.json)、[分析](device-info-analysis-2026-10-12.json)：601 B一致，包含已有112 B，新增489 B，累计1486个不同映射字节。两个会话均59 ACK、结束帧/正文完整。实际容量查询参数`/SD:`，版本常量`010004`，模型串`xink_test`；完整容量算术与字段来源见[报告](../device-info-fields.md)。仅证明文件系统卷容量，不是物理存储或固件分区备份。

[存储诊断候选审计](../storage-diagnostic-candidates.md)发现部分看似日志/只读路径可能flush存储，未执行；[VTOR审计](../vector-base-read-audit.md)确认架构地址与对齐32位读取要求，但实机特权/核心仍未完全确认，未读取该寄存器。CoMi App登录按用户要求暂缓。

[结束状态](device-info-final-state-2026-10-12.json)：FW010004、idle、容量59634/59632、noise9；未重启/刷写。`just check`通过56测试+24子测试，wheel/sdist构建通过。

## 第十二轮：从卷名到实际FAT容量回调

[首次](storage-first-2026-10-12.json)、[重读](storage-second-2026-10-12.json)、[分析](storage-analysis-2026-10-12.json)：937 B完整一致，其中336 B新增，累计1822个不同映射字节（含40 B挂载RAM元数据）。证实实际VFS通过mount+1c→vtable+44间接调用，定位`/SD:`挂载对象与callback `100a42d7`，成功分支按512逻辑扇区和FAT簇计算统计。[完整报告](../storage-binding-readback.md)。

没有取得底层芯片ID、固件分区表或完整备份。RAM两次相同只是会话快照，不代表原子冻结或重启后仍有效。新增指针变化阻止继续解引用的测试；`just check`通过58测试+24子测试，wheel/sdist构建成功。没有执行新的文件系统操作或写入。

[结束状态](storage-final-state-2026-10-12.json)：FW010004、idle、容量59634/59632、noise9，设备正常响应。

## 第十三轮：exFAT簇、磁盘registry与MMC_1

[首次](disk-first-2026-10-12.json)、[重读](disk-second-2026-10-12.json)、[分析](disk-analysis-2026-10-12.json)：1487 B一致，新增550 B，累计2372不同映射字节。查到exFAT type4/drive4、128 KiB簇、有效空闲簇缓存、唯一名为SD的disk_info；状态callback引用设备`sd`，其配置名和控制器对象均为`MMC_1`。[实机报告](../disk-registry-readback.md)；[卡元数据/分区路线源码审计](../sd-metadata-candidates.md)。

`disk_metadata`复算59634/59632 MiB，与独立[结束状态](disk-final-state-2026-10-12.json)相同；FW010004、idle、noise9。无新内部函数调用、重启或刷写；不能把所有容量查询概括为物理上无写，缓存失效路径的源码边界已记录。60测试+24子测试通过，wheel/sdist构建成功。

## SD/MMC状态与卡类别

[首次](card-first-2026-10-12.json)、[重读](card-second-2026-10-12.json)、[分析](card-analysis-2026-10-12.json)：2031 B一致，新增544 B，累计2916不同映射字节。实际指令定位driver状态，type=0与SD枚举/低功耗类型分支吻合；512 B、122138624扇区与disk_info一致。控制器配置base常量40058000；未访问MMIO。[报告](../card-state-readback.md)、[结束状态](card-final-state-2026-10-12.json)。

## 独立Flash对象与device表

[首次](boot-first-2026-10-12.json)、[重读](boot-second-2026-10-12.json)、[分析](boot-analysis-2026-10-12.json)：2931 B一致；新增867不同映射字节，累计3783 B。31项设备表含spi_flash、sim_flash、CDC_ACM；spi_flash ready、布局配置32 MiB，尚未验证JEDEC ID或启动来源。[报告](../boot-storage-device-readback.md)、[结束状态](boot-final-state-2026-10-12.json)。

## NOR缓存ID与配置容量差异

[首次](nor-first-2026-10-12.json)、[重读](nor-second-2026-10-12.json)、[分析](nor-analysis-2026-10-12.json)：3101 B一致，新增170 B，累计3953不同映射字节。缓存ID16405e、flags0；Zbit原厂32 Mbit系列资料与ID相符，不能把driver32 MiB配置视作物理容量。[报告](../nor-driver-readback.md)、[原厂来源](zbit-id-sources-2026-10-12.json)、[结束状态](nor-final-state-2026-10-12.json)。

## 日志服务回调与协议入口

[首次](shell-first-2026-10-12.json)、[重读](shell-second-2026-10-12.json)、[分析](shell-analysis-2026-10-12.json)：345 B一致，新增276 B，累计4229不同映射字节。实际timer callback存储与协议头检查已确认；尚未到shell表或分区表。[报告](../shell-service-readback.md)、[结束状态](shell-final-state-2026-10-12.json)。

## TLV文本到shell执行入口

[首次](shell-text-first-2026-10-12.json)、[重读](shell-text-second-2026-10-12.json)、[分析](shell-text-analysis-2026-10-12.json)：777 B一致，新增432 B，累计4661不同映射字节。文本type1到shell execute及内部执行callee已定位；命令表未读。[报告](../shell-text-readback.md)、[结束状态](shell-text-final-state-2026-10-12.json)。

## shell registry与dbg静态表

[首次](shell-registry-first-2026-10-12.json)、[重读](shell-registry-second-2026-10-12.json)、[分析](shell-registry-analysis-2026-10-12.json)：1535 B一致，新增758 B，累计5419不同映射字节。13项root registry、dbg descriptor及静态子命令数组指针已确认；子命令数组未读。[报告](../shell-registry-readback.md)、[结束状态](shell-registry-final-state-2026-10-12.json)。

## 实机ACPT分区表

[首次](partition-first-2026-10-12.json)、[重读](partition-second-2026-10-12.json)、[分析](partition-analysis-2026-10-12.json)：2987 B一致，新增1452 B，累计6871不同映射字节。完整744 B ACPT缓存表CRC703f5674，18项NOR配置覆盖4 MiB；不等于原始Flash镜像。[报告](../partition-readback.md)、[结束状态](partition-final-state-2026-10-12.json)。

## 启动安全标志源码审计

[固定SDK来源摘录与原文件SHA256](boot-security-source-audit-2026-10-12.json)、[解释及实机边界](../boot-security-source-audit.md)。无新增设备I/O；区分ACPT加密声明、镜像签名路径、CRC映射和OTA写标志。

## 启动SRAM候选交叉核对

[首次](boot-info-first-2026-10-12.json)、[重读](boot-info-second-2026-10-12.json)、[分析](boot-info-analysis-2026-10-12.json)：3051 B一致，新增64 B，累计6935不同映射字节。SDK-layout候选的param_save/system/nor字段匹配实机ACPT，param_phy=0不匹配；不等于完整ABI证明。[报告](../boot-info-readback.md)、[结束状态](boot-info-final-state-2026-10-12.json)。

## 当前映射ACTH镜像头

[首次](image-header-first-2026-10-12.json)、[重读](image-header-second-2026-10-12.json)、[分析](image-header-analysis-2026-10-12.json)：3571 B一致，新增520 B，累计7455不同映射字节。512 B头部加法校验通过，vector reset与entry1002d819匹配；正文checksum尚未验证。[报告](../image-header-readback.md)、[结束状态](image-header-final-state-2026-10-12.json)。

## 多行header读取验证

[64 B](header-batch64-first-2026-10-12.json)、[256 B](header-batch256-first-2026-10-12.json)、[512 B首次](header-batch512-first-2026-10-12.json)、[重读](header-batch512-second-2026-10-12.json)、[分析](header-batch-analysis-2026-10-12.json)：均与独立单行头部一致，无新增覆盖；[报告](../header-batch-readback.md)、[结束状态](header-batch-final-state-2026-10-12.json)。

## 完整recovery与应用交接（2026-10-13）

[报告](../recovery-complete.md)；[原始镜像](recovery-complete-2026-10-13/recovery-raw.bin)、[明文镜像](recovery-complete-2026-10-13/recovery-decoded.bin)、[真实采集报告](recovery-complete-2026-10-13/acquisition-report.json)、[修正版离线复验](recovery-complete-2026-10-13/report.json)、[全部62组基线/结果](recovery-complete-2026-10-13/captures.tar.gz)、[124个SD文件清单](recovery-complete-2026-10-13/sd-files.json)、[六模块指令与literal](recovery-complete-2026-10-13/handoff.json)。63,288 B头/正文校验通过；未执行新代码、写NOR或验证恢复。

## 自建M4镜像与实际checker（2026-10-13）

[方法/边界](../minimal-firmware-image.md)；[构建记录](minimal-image-2026-10-13/build-report.json)、[重复构建](minimal-image-2026-10-13/reproducibility.json)、[原厂正例gzip](minimal-image-2026-10-13/original-system.bin.gz)、[正例来源/哈希](minimal-image-2026-10-13/original-system.json)、[自建948 B ACTH](minimal-image-2026-10-13/minimal-acth.bin)、[实际checker结果矩阵](minimal-image-2026-10-13/gate-results.json)。无设备I/O；局部准入，不等于硬件启动或恢复能力。

## 已知ROM文件导出与正常态入口盘点（2026-10-13）

[ROM方法/边界](../rom-sd-bridge.md)；[首读](rom-sd-bridge-2026-10-13/first-download.bin)、[重读](rom-sd-bridge-2026-10-13/second-download.bin)、[首读帧/状态](rom-sd-bridge-2026-10-13/first-report.json)、[重读帧/状态](rom-sd-bridge-2026-10-13/second-report.json)、[复验分析](rom-sd-bridge-2026-10-13/analysis.json)：两份336 B与旧ROM oracle完全一致，留下两个非音频SD文件，无模式切换或NOR写入。
[正常态入口结论](../normal-ram-entry-inventory.md)、[全部表项与候选直接代码](normal-ram-entry-2026-10-13.json)：13 root、15表、81子命令；host-only，未建立RAM执行合同。

## 部分LARK芯片定义恢复（2026-10-13）

[方法与边界](../lark-register-recovery.md)、[全部选定DWARF布局/来源](lark-register-layouts-2026-10-13.json)、[提取与M4编译验证](lark-register-validation-2026-10-13.json)。12组外设结构、47 IRQ常量，自包含header入库；9类跨ELF一致，未恢复base/bit/startup或建立CoMi兼容性。[正式DFP索引限定负结果](../platform-next-route-review.md)。无设备I/O。

## 固定 GitHub/Gitee SDK 与录音应用对照（2026-10-13）

[GitHub源码/构建分类](../github-sdk-followup-2026-10-13.md)与
[国内平台/录音工作流](../domestic-sdk-followup-2026-10-13.md)：新增两份GitHub SDK、
Gitee REC_JX3完整仓库及ATS3085E已编译ELF。新的平台选择/构建仍是M33；录音应用
共享media/stream接口，协议、编码器、流拓扑和DSP资源不同，不是CoMi固件。
[查询/树/clone收据](recorder-reference-2026-10-13/acquisition.json)、
[177个固定blob哈希](recorder-reference-2026-10-13/source-manifest.json)、
[ATS3085E构建产物哈希](recorder-reference-2026-10-13/ats3085e-build.json)。
获取脚本已实际核验全部177文件；无设备I/O，未构建或执行新SDK。

## 显式单文件删除：源码与主机验证（2026-10-13）

[协议合同](../file-deletion.md)：固定官方JS成员及片段哈希、官方纯frame/CRC函数产生的独立0d请求golden、通用ACK与完整列表目标缺失的区别。新增CLI仅按明确serial/文件名确认删除单个已列出文件；真实Connection回放测试包含列表截断、迟到ACK、SIGINT及不重试。无设备删除、格式化、解绑或恢复出厂操作；不是固件备份／恢复进展。

## 官方剩余管理请求与完整接口表（2026-10-13）

[固定源码合同](../remaining-client-contracts.md)：bind/unbind/format/factory-reset/phone-type的准确片段哈希、7个官方纯函数独立golden、23请求opcode覆盖表。管理CLI一次性补齐4个opcode／5项动作；提交后仍效果未验证、退出3。只做主机测试，无设备管理请求、登录、重置或擦除；不改变M4 BSP、整机备份和恢复缺口。
## Actual CLI SIGINT acceptance, 2026-10-13

[Single real-device trial](cli-download-cancel-hil-2026-10-13.json): productionCLI
c733e0b, ownedFW010004, exit130,4,416 B exact baseline prefix; fresh full56,912 B
and explicit offset suffix52,496 B match independent old export. Idle/settings/
7-file list unchanged. Raw audio/logs ignored; no automatic resume, worker-exit,
firmware backup or flashing claim. [Method and limits](../download-cancel-contract.md#actual-cli-sigint-validation-2026-10-13).

## 新增真机小文件通道，2026-10-13

[实测边界与复现](../live-board-tests-2026-10-13.md)：固定RAM4096大下载失败，尾128B通过；两份独立XIP32B及handler160B与原镜像匹配。公开[原始小样本与收据](sd-bootstrap-2026-10-13/)去掉私人录音列表。
[实际FatFs分支](comi-file-write-2026-10-13.json)支持<512B CPU复制路径；不认定旧全零的DMA根因。
[MTU128独立HCI收据](linux-mtu128-2026-10-13.json)确认降MTU仍缺125B；STOP未上wire，禁止将意图当发送证据。

## SD/NOR实测接续，2026-10-14

[收据](sd-nor-progress-2026-10-14.json)及[原始字节与离线复验](sd-nor-progress-2026-10-14/README.md)：七处代码守卫、历史printk上下文28B、尾512B、预热尾128B及失败3852B。baseline HCI17条通知与partial一致；boot/NOR producer未执行。保留失败报告、后置独立状态及派生父链，禁止补片或把历史数据称新快照。公开复验与36项私有原件hash复验均通过。

[CPU/DMA冻结边界](../log-ring-freeze-boundary-2026-10-14.md)及[静态证据](log-ring-freeze-boundary-2026-10-14.json)：实际19段代码、7段静态数据；独立复验通过。无超时排空/UART等待、恢复错误忽略及writer/PM静止合同缺失，不能把CPU模式当分段ring稳定锁；无实机切换或实际挂死结论。

[logsrv实际指针/上下文](../logsrv-context-live-2026-10-14.md)：三处新代码守卫96B、global4B、context32B；两次现场采样整体成功。rd=wr204、slot4长度139仅为历史元数据，未读槽正文。公开紧凑收据固定原件SHA，不公开录音列表/完整日志；复验只用仓库文件，无设备I/O。

[logsrv已知短读→slot→新SD512](../logsrv-slot-live-2026-10-14.md)及[固定收据](logsrv-slot-live-2026-10-14.json)：唯一一次真机整体通过，7ACK/F1、4/32/512B完整下载、nonce→完整已知代码行在L431内、容量下降1MiB其余状态相同。公开284B（guards/元数据/标记/代码行）；完整512私有保存并固定SHA。公开复验及12项私有原件hash复验通过，不等同完整私有packet重放，不声明一般512可靠性或NOR能力。

[GPIO28 CTRL首次LDR32实读](../gpio28-word-live-2026-10-14.md)及[固定收据](gpio28-word-live-2026-10-14.json)：当前槽6完整观测1805，nonce→55B单字行在L406内，7ACK/F1、4/32/512B与前后完整info一致。首次连接发现超时、一次离线路径错误原件均保留；只有成功c执行GPIO读取。公开214B，fullslot512私有。公开复验/16私有hash通过；[后续1805配置表和路径](gpio28-remux-static-2026-10-14.json)9段实际镜像字节复验通过，未证明本次写入历史或物理UART可用。

[slot0映射两字实读](../map0-entry-live-2026-10-14.md)及[收据](map0-entry-live-2026-10-14.json)：1000000f/00024000两个独立时点，各自完整验收。失败context32及后续新context-b分开保留；公开392B，两个fullslot512仅hash。公开/19私有源hash复验通过，actual recovery读取/OR1/caller低f模板原字节复验通过。不声明原子entry、窗口尺寸、raw alias或整片备份。
