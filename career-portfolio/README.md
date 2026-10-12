# 数据分析与软件测试项目作品集

四个可运行的个人实战/行业练习项目，用于展示业务理解、代码实现、指标口径、用例设计和结果复核。采用大型互联网产品常见的电商、零售、客服工单场景，**不代表参与过相关公司的真实业务**。所有数据、账号与订单均为合成或演示数据。

| 方向 | 主项目 | 小项目 |
|---|---|---|
| 数据分析 | [电商用户行为与交易分析](analytics/README.md) | [零售门店销售日报与异常分析](retail-mini/README.md) |
| 软件测试 | [电商购物流程 Web 自动化测试](web-tests/README.md) | [客户工单管理接口测试](ticket-api/README.md) |

## 已验证的交付结果

| 项目 | 数据或测试规模 | 可查看的证据 |
|---|---|---|
| 电商分析 | 1,000 用户、33,227 有效事件、4,771 有效提交订单；12 项测试 | [指标 JSON](analytics/outputs/metrics.json)、[指标字典](analytics/METRICS.md)、[HTML 报告](analytics/outputs/report.html) |
| 零售分析 | 8 店 × 60 天、5,760 行流水、480 条日报；9 项测试 | [指标 JSON](retail-mini/reports/retail/metrics.json)、[异常 CSV](retail-mini/reports/retail/anomalies.csv)、[HTML 报告](retail-mini/reports/retail/report.html) |
| 电商 Web 测试 | 18 条浏览器用例、9 条业务单元测试 | [用例与运行说明](web-tests/README.md)、[执行 JSON](reports/web/results.json)、[HTML 报告](reports/web/index.html) |
| 工单接口测试 | 15 条真实 HTTP 集成测试 | [接口契约](ticket-api/README.md)、[执行 JSON](ticket-api/reports/results.json)、[HTML 报告](ticket-api/reports/results.html) |

GitHub 文件页可以查看代码和 JSON/CSV。HTML 报告需要下载项目后用浏览器打开，全部为离线文件，不依赖外部图表服务。

## 环境准备

推荐 Python 3.12、Node.js 20+。Python 标准库内的 SQLite 已满足项目需要，无需独立安装数据库。

```powershell
git clone https://github.com/lu-13-debug/lu-learning.git
cd lu-learning/career-portfolio
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npx playwright install chromium
```

Linux/macOS 激活虚拟环境使用 `source .venv/bin/activate`，浏览器安装可用 `npx playwright install --with-deps chromium`。Windows 浏览器测试默认选择已安装的 Edge，其他系统选择 Playwright Chromium。

## 一次复现四个项目

在 `career-portfolio` 目录执行：

```powershell
python -m analytics.run
python -m unittest analytics.tests.test_analysis -v
python retail-mini/run.py
python -m unittest discover -s retail-mini/tests -v
python -m unittest discover -s webshop/tests -v
npm run test:web
python ticket-api/run_tests.py
```

工单测试脚本以自身目录为基准管理测试文件。不要同时运行多份工单测试进程。Web 测试每次使用独立数据库和动态端口，自己启动并关闭服务及浏览器。

## 面试展示路径

数据分析：先展示报告回答业务问题，再解释漏斗、退款和留存口径，最后展示 SQL/Pandas 对账与边界测试。零售异常是主动注入的练习样例，不用它声称真实业务收益。

软件测试：先走一次购物链路，再执行18条页面用例；展示 Page Object、错误定位和订单 SQL 核验；最后展示工单状态流转、账号隔离与真实 HTTP 测试报告。单一浏览器下的通过结果不代表全浏览器或生产安全验收。

每个模块 README 提供可复述的讲解顺序与局限。开始投递前，应亲自运行并能解释代码、需求、测试失败原因和指标计算，而不是只记住简历里的数字。
