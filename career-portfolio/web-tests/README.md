# 电商购物流程 Web 自动化测试

围绕登录、商品搜索、购物车和下单流程，使用 Playwright 与 Page Object 构建浏览器回归测试；配套 Python + SQLite 本地商店，将页面断言与订单数据库核验结合。

## 核心功能

- 18 条浏览器用例覆盖正常购物、错误凭据、空输入、未登录加购、数量边界、售罄、空车结算、地址校验与退出。
- Page Object 集中封装登录、搜索、加购及结算，采用角色、标签和 Test ID 定位。
- 每条用例独立 BrowserContext；每次执行使用独立数据库和动态端口。
- 完整下单场景提取页面订单号，用 SQL 核对订单主表金额、明细金额和商品明细数。
- 9 条业务单元测试检查整数金额、重复下单幂等、库存不足回滚、参数绑定与订单隔离。
- 自动启动/关闭服务与浏览器，支持编号筛选；失败保存截图、Trace 和错误堆栈，输出 JSON/HTML 报告。

## 技术栈

Node.js 20+、Playwright 1.62.1、JavaScript、Python 3.10+ 标准库 HTTP、SQLite、unittest。

## 安装与运行

```powershell
git clone https://github.com/lu-13-debug/ecommerce-web-automation.git
cd ecommerce-web-automation
npm install
npx playwright install chromium
python -m unittest discover -s webshop/tests -v
npm run test:web
```

Windows 默认使用已安装的 Microsoft Edge，Linux/macOS 默认使用下载的 Chromium。Windows 使用下载的 Chromium 时，先设置 `$env:PLAYWRIGHT_CHANNEL='chromium'`；指定自定义 Python 路径可设置 `$env:PYTHON_BIN='C:\path\to\python.exe'`。

```powershell
# 只运行完整下单与 SQL 对账场景
$env:TEST_FILTER='WEB-16'
npm run test:web
Remove-Item Env:TEST_FILTER
```

验证执行器启动失败处理：`node web-tests/test-runner-error.cjs`。该命令检查无效浏览器通道能否返回非零退出码并将报告记录为 `infrastructure_error`；随后重新执行正常套件以刷新报告。

## 本地商店

```powershell
python -m webshop.app --port 8765
```

打开 `http://127.0.0.1:8765`，演示账号 `demo`，密码 `Demo123!`。商品、地址与订单为本地演示数据；每次登录建立独立练习会话。

## 用例范围

| 编号 | 场景 |
|---|---|
| WEB-01—04 | 首页、正确登录、错误密码、空账号密码 |
| WEB-05—07 | 搜索、无结果、未登录加购 |
| WEB-08—12 | 加购金额、修改数量、数量 0/21、移除商品 |
| WEB-13—15 | 售罄、空车下单、过短地址 |
| WEB-16 | 完整购物链路、订单 SQL 对账、购物车清空 |
| WEB-17—18 | 退出后下单受限、浏览器上下文与购物车隔离 |

## 目录与结果

```text
webshop/                  Python HTTP 应用、SQLite 业务与页面
webshop/tests/            9 条业务测试
web-tests/pages.cjs       Page Object
web-tests/cases.cjs       18 条浏览器用例
web-tests/run.cjs         测试执行器与报告
web-tests/test-runner-error.cjs  启动失败回归
reports/web/              JSON、HTML 与页面预览
package.json
```

默认执行结果为 18 条 Edge 浏览器用例通过、9 条业务测试通过。下载后查看 [HTML 报告](https://github.com/lu-13-debug/ecommerce-web-automation/blob/main/reports/web/index.html)、[JSON 结果](https://github.com/lu-13-debug/ecommerce-web-automation/blob/main/reports/web/results.json)。报告记录浏览器版本、执行时间、逐条状态与耗时，失败案例附截图和 Trace；失败退出码非零。
