# 电商 Web 页面自动化测试

个人实战项目，围绕互联网电商常见的登录、搜索、购物车和下单流程设计，使用本地演示应用，不关联任何公司业务。

## 技术与职责
- Playwright + JavaScript：真实浏览器操作与元素断言。
- Page Object：`pages.cjs` 统一封装登录、搜索、加购和结算操作，`cases.cjs` 维护18个独立业务场景。
- Python 标准库 HTTP + SQLite：提供可复现的被测页面和业务接口。
- 每条测试创建独立 BrowserContext；每次测试执行器生成独立数据库，并自动启动/关闭自己创建的服务和浏览器。
- `WEB-16` 从页面获取订单编号，用 SQL 对账订单主表总金额与明细金额、件数。
- 失败时保存截图、trace 和错误堆栈；HTML 与 JSON 报告记录逐条结果和耗时。

## 从仓库根目录运行
要求 Python 3.10+、Node.js 20+。

```powershell
cd career-portfolio
npm install
npx playwright install chromium
npm run test:web
```

Windows 默认使用已安装的 Microsoft Edge；Linux/macOS 默认使用 Playwright Chromium。Windows 如希望使用下载的 Chromium，可修改 runner 的 channel 选择；指定其他已安装通道可设置环境变量 `PLAYWRIGHT_CHANNEL`。Python 非默认路径时：

```powershell
$env:PYTHON_BIN='C:\path\to\python.exe'
npm run test:web
```

结果：`reports/web/results.json`、`reports/web/index.html`。报告使用真实执行结果，失败返回非零退出码。

服务或浏览器启动失败时也会覆盖本次报告，明确记录 `infrastructure_error`，不会保留上次通过的结果冒充本次。执行器失败行为回归验证：`node web-tests/test-runner-error.cjs`；该命令有意启动无效浏览器通道并检查失败报告，之后应再运行正常套件刷新报告。

单独体验被测应用：

```powershell
python -m webshop.app --port 8765
```

浏览器打开 `http://127.0.0.1:8765`，演示账号 `demo`，密码 `Demo123!`。每次登录产生独立练习空间，这不是真实账号系统或生产权限架构。

## 18 个自动化用例

| 编号 | 验证场景 |
|---|---|
| WEB-01 | 首页商品与演示标识 |
| WEB-02 | 正确账号登录 |
| WEB-03 | 错误密码 |
| WEB-04 | 空账号和密码 |
| WEB-05 | 关键字搜索 |
| WEB-06 | 搜索空结果 |
| WEB-07 | 未登录加购 |
| WEB-08 | 加购数量与金额 |
| WEB-09 | 更新数量重新计价 |
| WEB-10 | 数量0校验 |
| WEB-11 | 数量超过20校验 |
| WEB-12 | 移除购物车商品 |
| WEB-13 | 售罄按钮禁用 |
| WEB-14 | 空购物车下单 |
| WEB-15 | 过短地址校验 |
| WEB-16 | 完整下单与SQL落库核对 |
| WEB-17 | 退出后下单受限 |
| WEB-18 | BrowserContext与购物车隔离 |

## 业务单元测试

```powershell
python -m unittest discover -s webshop/tests -v
```

九个测试额外检查整数金额、下单幂等、库存不足整单回滚、SQL参数化、订单隔离等边界。

## 面试演示建议
1. 用页面走一次搜索、加购、下单，解释金额以整数分存储的原因。
2. 执行自动化并打开 HTML 报告，展示正常和异常路径。
3. 展示 `WEB-16` 的页面断言与 SQL 核对。
4. 修改一个页面按钮名称或业务规则，运行筛选用例观察失败截图和 trace，再恢复。

```powershell
$env:TEST_FILTER='WEB-16'
npm run test:web
Remove-Item Env:TEST_FILTER
```

这组用例验证所列练习需求，不包含真实支付、性能压测或生产安全验收；未声称全浏览器覆盖或发现真实线上缺陷。
