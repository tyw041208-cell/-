# G0 开发与验证报告

日期：2026-11-17，展示时区 Asia/Seoul。实验版本 G0-1。

**总体结论：BLOCKED。离线实现和测试已完成，真实数据与会计验收未完成，不建议 G0 PASS，不进入 TASK_002。**

## 当前基线与范围

完整阅读上传的 AGENTS.md、V0_PRD.md、TASK_001.md、PROJECT_MASTER.md；原文件逐字复制保留在项目根目录。主记录开头当前有效基线及21、22节优先于旧章节。本轮明确指令及 TASK_001 限定为八 ETF 数据资格、SPY 开发窗会计；历史策略与框架建议没有转为开发任务。README_START.md 也已阅读。

项目目录 `/workspace/work/g0`，独立于附件目录，不覆盖用户附件。当前 `/workspace` 虽有受保护 `.git` 目录，但 `git status` 返回 not a git repository，没有假装已关联 GitHub 仓库，也未修改该 `.git`。Python 虚拟环境 `.venv` 用已有系统 Python 创建；无第三方包安装、无系统设置修改。初次附件下载工具报告工作区未就绪，环境 ready 后重试成功，没有丢失文件。

## 环境与执行记录

| 项目 | 真实结果 |
|---|---|
| 系统 | Debian GNU/Linux 13.6，Linux 6.18.57 x86_64 |
| Python | 3.12.14，虚拟环境运行与文件读写成功 |
| Git | 2.52.0，命令可运行；当前目录不是项目仓库 |
| 依赖 | 仅标准库；requirements.txt 记录版本及不安装的理由 |
| 云端 LEAN | 无本地运行时；没有启动实际云端任务 |
| QuantConnect 账号/数据权限 | 未登录、未授权、无法验证实际额度 |
| GitHub | 本轮不需 GitHub API；没有推送或创建远程仓库 |

本轮实测主要命令与结果：

```sh
python3 --version                         # 3.12.14
 git --version                            # 2.52.0
 git status --short                       # 失败：当前不是仓库
python3 -m venv work/g0/.venv              # exit 0
cd /workspace/work/g0
.venv/bin/python tools/build_cloud.py      # exit 0
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src tests tools quantconnect
.venv/bin/python tools/compare_samples.py reports/evidence/independent_samples.csv
.venv/bin/python tools/verify.py
```

最终实际命令、退出码、Python 和平台信息见 `evidence/local_verification.json`；完整离线日志见 `evidence/unittest.log`、`compile.log`、`sample_comparison.log`。`source_sha256.json` 记录代码/配置/测试指纹。没有用合成价格输出任何真实回测业绩。

## 交付实现

- `src/quant_g0/core.py`：日历预期集合核对、覆盖、缺失、重复、OHLC/非正/非有限价格、成交量、数据指纹；RAW 整股账本、分红与拆股、预留费用、现金守恒、独立日志重建、时间窗门禁。
- `quantconnect/main.py`：可整文件粘贴至 QuantConnect Python 项目的单文件算法；八 ETF 事件流与公司行为统计，2010–2025质量检查，SPY 2010–2019会计。没有订单接口调用，拒绝 live_mode。
- `quantconnect/adapter.py`、`tools/build_cloud.py`：维护源及可复现的单文件生成器。
- `config/g0.json`：预登记时间窗、八标的、RAW、费用情景、抽样日、0.01美元对账容差及未知成本。
- `tests/`：核心与云端适配的离线契约测试；fake API 清楚标明不是 LEAN 实测。
- `tools/compare_samples.py`、两个证据 CSV 模板：独立合法来源核对入口，空证据拒绝通过。
- `README.md`：中文本地命令、免费云端项目创建/粘贴/运行/日志操作、许可限制、口径及 API 未验证说明。

## 真实测试结果

首轮核心单元测试 25/25 通过。加强独立账本重建后，最终 28/28 通过，失败0、跳过0。包括 25 项核心用例和3项适配契约测试：生成文件一致性、无订单/网络/策略绩效方法、模拟2023数据不改变开发窗账本。非法价格等用例含多个子案例，不额外夸大测试总数。

| 验证 | 结果 | 证据与限制 |
|---|---|---|
| 文件读写/虚拟环境 | PASS | 真实创建代码、生成文件及日志，虚拟环境运行成功 |
| 离线测试 | PASS | 28个 unittest，通过；全为合成数据或静态检查 |
| Python语法编译 | PASS | compileall exit 0；不代表 AlgorithmImports 可导入或 LEAN 可运行 |
| 空独立证据拒绝通过 | PASS（拒绝行为） | 比较程序真实 exit 1；实际比较结论 BLOCKED，0个价格日期、0个分红事件 |
| 八ETF真实数据 | BLOCKED | 未有云端统计，不能给出真实缺失率、股息数、拆股数或上市日期 |
| 独立五价格日/两分红 | BLOCKED | 未取得两源实值及来源许可；模板没有伪造数据 |
| 真实开发窗会计 | BLOCKED | 未获得真实输入；云端脚本待执行 |
| 平台持仓对账 | BLOCKED | 本实现使用影子账本与独立计算路径，不提交平台订单，不能冒称已与平台投资组合一致 |
| 最终留出安全边界 | PASS（代码与合成检查） | 2020之后禁止会计估值；2023–2025只做质量计数，无策略排名 |
| 全口径净收益 | BLOCKED | 真实投资收益、税费、汇兑、数据/API/运维费用未知；不输出数字 |

最后一个比较命令退出1是预期的证据缺失，不是测试通过意义上的真实数据合格；verify.py 对“正确拒绝空证据”的 PASS 与独立验证本身的 BLOCKED 分开。

## 会计假设及适用限制

USD 10000 初始现金，首个观察日收盘形成固定持有信号，下一观察交易日开盘影子买入整股；手续费0或每笔1美元（示例假设）；剩余现金保留、现金利息0（假设）、不再投资股息、不卖出。RAW 加 LEAN 除息日入现金；这不是实际付款日/税后现金验证。拆股按 LEAN 价格因子处理；涉及零股的反向拆股若缺少可信现金补偿价，主动阻塞。

独立日志重建使用买入股数/价格/费用及分红/拆股原始事件重新计算，不读取可变现金与持仓字段。误差容限在真实运行前固定0.01美元；内部Decimal保留精度。此方式可发现现金与股数漂移，但共享相同事件输入，不能排除供应商事件本身错误，也不等于另一供应商或平台验证。

为了不生成2010–2025策略绩效，未在平台投资组合持有SPY，平台现金曲线不能作为SPY结果。云端输出只包含开发窗影子账本期末现金、股数、净值与重建最大误差。真实税/滑点/价差/汇兑和研发成本没有计量，不能据此宣称可投资盈利。

## 文档核查及失败/阻塞

2026-11-17访问 QuantConnect 官方免费层、许可、公司行为、证券订阅及日历公共文档；链接与 API 说明在 README。官方页面描述个人 Free 组织有一研究、一回测节点；云内行情许可不等于本地下载许可。账号实际资格仍未验证。

历史数据 equity 页面一次访问失败（工具返回 inaccessible）；没有编造其内容。最终实现不调用 history。当前未获得可执行的 QuantConnect 连接、云端 LEAN 或合法真实价格输入，未绕过登录或下载限制。`is_date_open`、日线 precise end、字典映射和 Python/.NET 兼容性须真实云端验证。

尚需证据：8资产证券身份及上市/成立日、独立日历复核、实际公司行为数量和有效性、真实5日价格/2次分红对照、云端日志及运行引擎版本、数据许可确认、实际开发窗会计。任何一项缺失，不把 G0 标成 PASS。未发生购买、券商连接、真实订单、策略筛选或最终留出策略绩效访问。

## 用户下一步（最小行动）

1. 按 README 在 QuantConnect Free 新建 Python 算法项目，复制整个 `quantconnect/main.py`，仅运行 Backtest；不升级、不连接券商。
2. 提供完整编译/运行异常或允许复制的 G0 聚合日志、引擎版本、项目/回测标识。若额度不足或要求付费，停止并带回提示。
3. 核实发行人身份/上市日期与授权的独立来源；统一未复权收盘价、除息日每股金额，按预登记容差完成至少5日价格及2次分红。仅复制许可证允许的小量样本/差异，不能下载受限历史。
4. 将报告、日志和证据带回审查。补齐实际证据前 G0 保持 BLOCKED；之后仍须审查，不自动开展 TASK_002。

## 交付路径限制

应用预设 `/codex/.../output` 目录在本执行环境不存在；尝试创建时系统返回 Read-only file system。不是项目测试失败，也不是账号授权问题。交付改存可写的 `/workspace/output`，不修改系统挂载或权限。
