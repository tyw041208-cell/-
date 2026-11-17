# G0-R01 独立代码审查整改报告

日期：2026-11-17；时区 Asia/Seoul。**结论：BLOCKED，等待独立复审。**

本报告为当前有效整改结果；原 G0 报告及28项测试证据保存在 `evidence/pre_r01/`。本次不把本地合成测试通过描述为真实数据资格通过。

## 变更范围

基于交付提交 `5cd3075`，在独立分支 `g0-r01` 修复两项审查发现。资产池、2010–2025质量窗、2010–2019会计窗、五个价格抽样日、RAW、整股、USD10000、0/1美元费用、零利息及下一观察交易日开盘的会计假设均未改变。无采购、真实账户、真实订单、留出策略收益访问或 TASK_002 开发。

## R01-1：独立账本重建

旧实现虽然没有直接读取当前持仓计算股息，但仍使用分红事件中的 original_qty 和拆股记录中的 original_qty/whole 作为输入，存在同源错误被重复接受的问题。已修复：

- 从初始现金和零持仓独立重放；买入数量依据重建现金、原始成交价与冻结费用重新计算，不采用日志买入数量作为真值。
- 分红依据重建自身持仓乘原始每股分红计算；记录的分红持仓只用于相等性检查。
- 拆股从重建自身股数除以原始拆股因子，独立向下取整、计算零股及现金补偿；原拆前/拆后数量只作为待核对结果。
- 逐事件比较原现金增量、记录股数和重建结果，原日志输出字段有差异立即判失败，即使差异小于美分。期末现金、股数市值和净值仍按原0.01美元容限核对，禁止调用方放宽容限。
- 拒绝未知/损坏/非有限事件、事件倒序、未来事件和重复同日公司行为。缺少合法零股补偿价仍阻塞，不补造。

原始成交价、分红单位金额、拆股因子与补偿价仍是共享输入；若这些输入和全部输出被一致改写，纯本地重放不能证明真实性。需外部供应商证据和平台核对；本修复不声称建立防篡改签名或平台持仓对账。

## R01-2：独立样本验收

- 价格样本必须为 SPY、RAW、close，日期集合严格等于 `config/g0.json` 已登记的2010-01-04至2010-01-08五日，任意替换或额外价格日期被拒绝。
- `sample_tolerances` 将原 README 中已说明的容差明确锁定到配置：价格0.01美元、分红0.000001美元、拆股因子0.00000001。配置值同时与代码冻结值核查；CSV容差必须数值相等，扩大或缩小都被拒绝。不是修改实验成本/时间/资产参数。
- 分红必须为SPY、distribution，日期严格对应完整开发窗云端事件索引中最早两次事件，QC金额亦须与该索引一致。重复行、错误标的/字段、篡改容差、后续分红替换首两次均拒绝。
- 云端增加 `G0_DIVIDEND_REFERENCE`：开发窗观察到的全部分红日期及最早两次金额。要求日期唯一有序、开发窗覆盖检查通过；比较工具接收独立于样本CSV的参考JSON。缺参考或样本不齐时为 BLOCKED；结构无效、索引不完整、篡改或超差为 FAIL/拒绝。
- 该索引只证明当前事件流选择一致性，不能自动证明供应商没有漏掉公司行为，也不能自动鉴定来源独立性或许可证。真实独立核对仍待完成，不编造最早两次真实分红日期。

## 测试与执行证据

运行环境：Python 3.12.14、Git 2.52.0、Debian13.6。使用现有标准库，无新依赖、无安装。工作目录 `/workspace/work/g0-github-delivery`。

```sh
python3 tools/build_cloud.py
python3 tools/verify.py
```

verify.py 实际执行：

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests tools quantconnect
python3 tools/compare_samples.py reports/evidence/independent_samples.csv
```

| 检查 | 真实结果 |
|---|---|
| 首轮整改测试 | 59项通过，失败0、跳过0 |
| 增加字段/重复/配置不变检查后 | 63项通过，失败0、跳过0 |
| 最终完整测试 | **64项通过，失败0、跳过0，退出码0** |
| 语法检查 | compileall退出码0 |
| main.py生成一致性 | 单文件等于核心源码+配置+适配器，测试通过 |
| 缺真实样本的CLI | 真实输出BLOCKED，退出码1，为预期拒绝；不代表样本验证通过 |
| 交付ZIP | 打包后CRC检查及逐文件字节核对通过 |

针对性反例包含：伪造分红持仓并同步篡改现金；伪造拆前/拆后股数及零股现金；单改日志现金增量；改买入数量并同步改持仓；重复公司行为并同步改现金；未知事件、NaN、未来/倒序事件；非预登记价格日、重复价格/分红、错误标的/字段、挑选后续分红、参考QC金额篡改、三类容差扩大及收紧、参考索引倒序/留出日期/不完整、临界容差和超差。

`reports/evidence/unittest.log` 是最终完整真实测试日志，`local_verification.json` 记录实际命令/退出码，`source_sha256.json` 记录源码/配置/测试指纹，`sample_comparison.json` 记录当前真实空证据结论。历史证据保留在 `pre_r01`，不得误认为本次64项日志。测试中分红日期和金额均明确为合成fixture，不是真实市场证据。

## 修改文件清单

核心/配置/适配：`src/quant_g0/core.py`、`config/g0.json`、`quantconnect/adapter.py`、重新生成的 `quantconnect/main.py`。

测试/工具：`tests/test_core.py`、`tests/test_cloud.py`、新增 `tests/test_r01.py`、`tools/compare_samples.py`。

文档/证据：`README.md`、本报告、`reports/evidence/independent_samples.csv`、`local_verification.json`、`sample_comparison.json`、`sample_comparison.log`、`source_sha256.json`、`unittest.log`，新增 `pre_r01` 历史证据。重新生成根目录 `G0_DELIVERY.zip` 和 `SHA256SUMS.txt`，避免整改分支附带旧代码压缩包。Git提交详情为完整改动清单。

## 剩余阻塞与用户操作

1. 未运行真实 QuantConnect Cloud/LEAN；main.py 已生成并通过本地语法/模拟契约检查，不能声称云端API和真实数据已运行通过。
2. 仍缺八ETF上市/身份、真实覆盖/独立交易日历、公司行为及数据许可证据。
3. 仍缺预登记五日真实RAW收盘价、开发窗最早两次SPY真实分红及独立授权来源。只有许可允许时复制G0_DIVIDEND_REFERENCE的JSON到 `reports/evidence/dividend_reference.json`，再按 README 运行比较；不得从待检CSV自行生成索引，不上传受限原始历史。
4. 真实开发窗会计与平台持仓对账仍未验证；真实成本、税费、汇兑和全口径经济净收益未知。
5. 用户将整改分支、Commit及日志交独立审查者复审；本轮保持BLOCKED，不自动开展TASK_002。
