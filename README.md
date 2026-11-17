# G0 数据资格与基准会计验证

当前版本：**G0-R02 云端兼容性整改**。当前结论：**BLOCKED，未完成真实数据验收**。本项目仅 TASK_001；不实施 G1、不做策略排名、不连接实盘。

## 本地运行（无需安装第三方包）

本次实测 Python 3.12.14、Git 2.52.0、Debian 13.6。项目在 `/workspace/work/g0`。这不是你的 Mac 本机检查结果。虚拟环境只隔离本项目，不修改系统 Python；没有运行 pip install。

解压交付包后，在该文件夹打开终端：

```sh
python3 -m venv .venv
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/build_cloud.py
.venv/bin/python -m compileall -q src tests tools quantconnect
.venv/bin/python tools/verify.py
.venv/bin/python tools/compare_samples.py reports/evidence/independent_samples.csv
```

最后一个命令在没有真实样本时**应返回 BLOCKED 和退出码 1**，不是已经通过。Windows 可使用 WSL；本次没有验证 Windows 原生命令。依赖只有标准库，`requirements.txt` 不要求安装包；云端 `AlgorithmImports` 由平台提供，不在本地伪装安装。云端引擎版本必须在实际运行时登记，不能声称已锁定。

## QuantConnect Cloud 操作步骤（中文）

1. 你自行打开 https://www.quantconnect.com/ ，注册或登录；不要把密码、令牌或券商资料交给 AI。确认个人组织为 **Free**，不绑定证券账户、不购买节点或数据。官方文档描述 Free 提供一个回测节点和一个研究节点，但你的账号资格与额度尚未实测。
2. 在 Algorithm Lab 创建新的 **Python** 算法项目，建议名称 `G0_DATA_ACCOUNTING_001`。不要选择 Live Trading；本任务只用 Backtest。
3. 打开本交付包 `quantconnect/main.py`，复制**整个文件**，替换新项目默认 `main.py`。单文件已包含配置与核心逻辑，无需复制本地 src、安装包或建立 notebook。不要粘贴 adapter.py，它不能独立运行。
4. 编译，启动 **Backtest**。日期已固定 2010-01-01 至 2025-12-31，八资产、日线、RAW、不前向填充、不预热。若需要付费、权限不足或提示配额，立即停止并记录提示，不升级、不绕过。
5. 脚本没有任何订单调用：平台投资组合保持现金，平台绩效面板**不是 SPY 基准结果**。真实数据驱动的 SPY 记账只在独立影子账本中计算到 2019 年；2020 年起不更新、不估值该账本。无需访问策略绩效面板。
6. 在 Logs 查找 `G0_CONFIG`、8 条 `G0_QUALITY`、`G0_CASH`、`G0_ACCOUNTING`、`G0_END`。`G0_SAMPLE` 是预登记的五个开发窗原始收盘价及最早两个 SPY 分红事件。先确认条款允许复制这些少量样本及聚合日志；不允许则仅云内人工比较，记录差异与许可结论，不下载原始历史。没有 `G0_END`、日志截断、API 异常或实际无数据均视为 BLOCKED。
7. 记录项目标识、回测标识、运行日期、平台 Python/LEAN 引擎版本、数据集及许可、完整异常、8资产统计。只有许可允许时，将日志复制为 `reports/evidence/cloud_run.log`。禁止批量转存原始价格，不使用 Object Store 导出规避权限。
8. 根据下节完成独立核对，将真实日志、独立证据及本地测试日志交回审查。不要自行改写报告为 PASS，不开始 TASK_002。

### API 与运行限制

采用当前官方 Python 风格 `initialize/on_data/on_end_of_algorithm`、`add_equity`、`DataNormalizationMode.RAW`、`Slice.dividends/splits/bars` 和 `SplitType.SPLIT_OCCURRED`。本地仅做语法与模拟适配契约检查，**没有真实 LEAN 运行**。`exchange.hours.is_date_open(datetime)`、`daily_precise_end_time` 及 Python/.NET 字典 `.get` 的具体运行兼容性须云端编译运行确认；若出错，请原样带回，不默默更换日历或填补数据。

日线以 `bar.time` 的交易所本地日期归属交易日；`bar.end_time` 才是完整 bar 可知的时刻。最早信号取首个日线结束，买入取后一个观察到的交易日开盘。这是历史会计模拟，读取下根 bar 后按其开盘建账，不是可实时成交的执行模型。缺失日会使数据质量门禁失败，即使会计仍可算也不能合格。

## 会计口径与限制

- USD 10000，整股，一次买入，不再投资分红、不卖出；零利息现金基准为 USD 10000，利率是零的假设。
- 固定每次买入费用分别为 USD 0 和 USD 1；1美元只是示例，不是券商报价。整股数量预留费用，剩余现金保留。无成交量冲击/价差/滑点、税、借券或汇兑真实数据，均不能声称真实全成本收益。
- RAW 价格加分红现金；采用 LEAN **除息日入现金**约定，不是实际付款日现金到账验证，实际现金可用性仍需后续证据。本任务无分红再投资；调整价模式被核心代码拒绝。
- 拆股使用 LEAN 因子约定 `新股数=旧股数/因子`。反向拆股若出现零股，需要独立可验证的拆后现金补偿价格，否则阻塞，绝不自行补造。
- 逐日用不同计算路径从交易与公司行为日志重建现金、股数和净值，预先冻结最大误差 0.01美元（美分显示精度）；内部 Decimal 不每日舍入。这个核对不能替代平台持仓对账：算法不下订单，因此平台对账项始终明确 BLOCKED。
- 不生成收益排名、Sharpe、回撤或留出净值；不输出2023–2025策略绩效。数据质量指纹仅用于同版本输入对比，不声称是供应商快照版本。
- 投资净 P&L 只有真实开发窗数据到位才可报告；数据/API/运维成本未知，全口径经济净收益为未验证；一次性开发成本未计量。没有人民币兑换报价，不生成 CNY 收益。

## 独立核对（不得用合成样本代替）

1. 对每只 ETF 从发行人官方基金页面/招募文件确认证券身份、基金成立日与交易所首次上市日，二者分别记录；2010首次数据不等于上市日。填写 `reports/evidence/asset_registry.csv`，记录 URL、访问日、许可、来源事实、日历和时区。模板不预填未经核实的日期。
2. 使用独立于 QuantConnect 数据链的合法来源：发行人官方历史分配记录核对 SPY 最早两个开发窗分红事件；独立授权行情源核对预定五日**未复权常规交易时段收盘价**。不同价格供应商不一定独立，记录底层供应商。不默认 Yahoo/Stooq/Alpaca 数据免费、独立或允许下载。
3. 如来源仅给 adjusted close，则不匹配，标 BLOCKED；不能悄悄换成复权价格。分红须统一每股美元、除息日期，不能将支付日当除息日。若无拆股则记录云端观察数及独立来源；无法确认不得写“没有拆股”。
4. `independent_samples.csv` 一行一事件，填写日期、kind（price/dividend/split）、qc_value、independent_value、normalization（raw）、source_url、license_note、tolerance、tolerance_reason。金额容差已按原说明锁定到配置：收盘价0.01美元、分红0.000001美元、拆股因子0.00000001；样本不能放宽或收紧。源精度不足应阻塞，不得修改容差使其通过。
5. 在查看真实数据前保留模板及配置指纹；真实数据两源都到位后运行 compare_samples.py。工具要求恰好配置中预登记的5个 SPY 原始收盘价日期，以及开发窗最早两次 SPY 分红事件；重复、错误日期/字段、容差篡改直接拒绝。超容差 FAIL、缺样本或缺完整云端事件索引 BLOCKED；该工具不自动判断来源独立性或许可证，仍需人工审查，不因比较通过就宣布 G0 PASS。

## 官方文档核查

2026-11-17（首尔日期）访问公共官方文档，未登录账户：
- 免费层及节点：https://www.quantconnect.com/docs/v2/cloud-platform/organizations/tier-features
- 数据云内使用与下载许可区分：https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing
- 公司行为与 Python API：https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/corporate-actions
- 美国证券数据：https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/algoseek/us-equities
- 日历：https://www.quantconnect.com/docs/v2/writing-algorithms/securities/market-hours

历史数据 equity 文档地址本次访问失败，未据此宣称 history API 验证。本项目采用事件流，不依赖该 API。实际账号数据授权、免费运行资源、数据覆盖和许可仍需平台确认。

## G0-R01：整改后独立样本验证

配置仅将既有文档容差明确写入 `sample_tolerances`，不改变资产、日期、金额或费用。CSV 新增 `symbol` 与 `field`；symbol 固定 SPY，field 分别为 close / distribution / factor。

真实云端完成后，只有许可允许时，从 `G0_DIVIDEND_REFERENCE` 日志复制其 JSON 部分到 `reports/evidence/dividend_reference.json`。事件索引包含完整开发窗中观察到的分红日期及最早两次的金额；不得从待比较 CSV 反向生成或自行挑选日期。complete 标志仅表示当前输入事件流覆盖/检查状态，不能证明供应商未遗漏事件，仍须独立来源审查。未取得真实索引时不要用合成测试 fixture 代替。

```sh
python3 tools/build_cloud.py
python3 tools/verify.py
python3 tools/compare_samples.py reports/evidence/independent_samples.csv reports/evidence/dividend_reference.json
```

账本重建不再采用原日志的分红持仓、拆股前股数或拆后股数作为计算输入，而以重建自身持仓计算，再逐项核查日志股数与现金增量。原始事件字段不一致即失败（即使金额差小于0.01美元）；0.01美元容限仅保留给期末状态对账。共同输入的价格、分红单位金额、拆股因子若被一致改写，仍需外部证据验证，本次修复不声称有密码学防篡改能力。

## G0-R02：Decimal / Bar 命名冲突修复

用户实际云端运行：项目39565431，LEAN Engine 2.5.0.0.18269，初始化在 Decimal(str(x)) 失败。原 AlgorithmImports 通配符在执行时覆盖了 Python Decimal；原离线平台stub没有导出冲突名称，未检出此问题。

现使用 PythonDecimal / PY_ROUND_FLOOR 明确别名，自定义 Bar 改为 G0DailyBar，平台只显式导入 QCAlgorithm、Resolution、TimeZones、DataNormalizationMode、SplitType。参数与会计逻辑未改变。

请使用 **g0-r02 分支**的 quantconnect/main.py 整文件替换项目39565431中的旧main.py，再运行 Backtest；不要仅修改云端一处而漏掉生成脚本。引擎保持用户实际版本，记录回测ID、编译与完整错误或G0日志。没有收到修复后的真实运行日志前，云端兼容性仍为BLOCKED；本地模拟通过不能替代真实LEAN运行。本轮未修改云端项目，也没有重跑实际回测。
