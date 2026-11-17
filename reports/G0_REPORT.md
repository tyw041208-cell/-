# G0-R02 QuantConnect Cloud 运行兼容性整改

**当前结论：BLOCKED，等待真实云端重跑及独立复审。**

本轮基于 G0-R01 提交 `9108cecaff9bdb15f9711ae829152a82b5b0e737`，独立分支 `g0-r02`。此前报告及64项测试日志保留在 `reports/evidence/pre_r02/`；更早证据仍在 `pre_r01/`。

## 已收到的实际失败

用户提供：QuantConnect项目ID **39565431**，LEAN Engine **2.5.0.0.18269**，首次实际回测初始化失败。用户报告位置为 main.py line25 的 `D = lambda x: Decimal(str(x))`，调用链 Ledger.__init__ → initialize line290；错误为 `Argument mismatch: argument 1 ('value') expected float, got str.`。编辑器同时报告自定义Bar与平台Bar命名冲突。

上述为用户报告的真实失败，不是本环境执行日志；未提供回测ID，不能编造。原信息存于 `reports/evidence/r02_cloud_failure_user_report.json`。此前报告“尚未运行云端”的状态已由本报告更新为“用户已实际运行，但初始化失败”；修复后是否兼容仍未验证。

## 根因与修复

生成器先写入core.py，再写入平台适配器。原适配器 `from AlgorithmImports import *` 会覆盖已绑定的Python Decimal；D函数调用时动态查找全局Decimal，因而实际调用了System.Decimal。自定义Bar也存在同类覆盖。原平台stub只提供少数名称，未覆盖该真实冲突场景，属于原测试不足。

修复内容：

- 标准库显式别名：`Decimal as PythonDecimal`、`ROUND_FLOOR as PY_ROUND_FLOOR`，D只引用PythonDecimal，整数股数舍入只引用Python常量。
- 自定义 `Bar` 全面重命名为 `G0DailyBar`，包含数据检查测试和适配器调用处，不增加旧名别名掩盖冲突。
- 平台改用明确导入：QCAlgorithm、Resolution、TimeZones、DataNormalizationMode、SplitType；生成文件不再含通配符导入。
- 重新生成 quantconnect/main.py；核心和适配器源文件保持为生成源。

config/g0.json 与R01逐字节相同。资产池、时间窗、五个价格日期、容差、原始价格+分红、USD10000、整股、费用0/1美元、现金利息0、后续观察交易日开盘建账等均未改变。无新依赖、付费、真实证券账户、真实订单、留出期策略绩效或TASK_002。

## 实际离线检查

执行目录 `/workspace/work/g0-github-delivery`；Python3.12.14，标准库，无软件安装。

```sh
python3 tools/build_cloud.py
python3 tools/verify.py
```

verify.py运行完整unittest、compileall、缺真实样本的比较CLI：

| 检查 | 实际结果 |
|---|---|
| 全部离线测试 | **68通过、0失败、0跳过**，退出0 |
| 语法编译 | compileall退出0 |
| 生成脚本一致性 | 单文件与源/配置一致，通过 |
| 原通配符问题最小复现 | 模拟System.Decimal拒绝str，同类错误成功复现 |
| 冲突导出隔离 | 模拟平台导出Decimal/Bar/ROUND_FLOOR，Python别名与自定义类保持正确 |
| 初始化和数据处理 | 同一模拟平台下initialize及两日on_data成功，零费100股、1美元费用99股，账本重建通过 |
| 禁止通配符回归 | 对生成文件进行AST检查，通过 |
| 缺真实独立样本 | 比较CLI真实BLOCKED，退出1（预期拒绝） |
| 交付包 | CRC及逐文件字节核对通过 |

测试仅模拟命名空间冲突，不含实际LEAN/.NET互操作、真实交易日历或真实行情验证。全部最终日志在 `reports/evidence/unittest.log`；实际命令与退出码在 `local_verification.json`，代码指纹在 `source_sha256.json`。不把模拟初始化成功称为真实Cloud回测通过。

## 剩余阻塞与最小下一步

1. 本环境没有访问用户QuantConnect项目或执行修复后云端回测，实际引擎兼容性仍BLOCKED。
2. 请将整改分支的整个quantconnect/main.py替换项目39565431的main.py，仅运行Backtest。保留LEAN版本、实际回测ID、编译信息和完整G0日志；如有新异常原样带回，不修改研究参数。
3. 八ETF真实质量统计、发行人上市/身份、独立日历、合法数据许可、预登记五日价格及最早两次分红独立核对、真实开发窗会计和平台持仓对账仍未通过。初始化失败不提供这些证据。
4. 原始事件输入真实性、来源独立性、实际付款日/税费/滑点/汇兑和经济净收益仍未知。保持G0 BLOCKED，等待独立复审，不进入TASK_002。
