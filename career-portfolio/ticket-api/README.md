# 客户工单管理接口测试

使用 Python 标准库搭建工单 API，并通过真实 HTTP 请求验证登录、创建、分页、状态流转、账号隔离和 SQLite 持久化，自动生成逐条测试结果报告。

## 核心功能

- 15 条 unittest 测试方法，通过 subTest 覆盖正常输入、长度边界和异常请求。
- 验证 `open → in_progress → resolved` 状态流转，拒绝跨级、重复流转和重新打开。
- 双账号检查列表、详情和修改权限；非法操作后直接核对数据库未发生变更。
- 检查错误 JSON、重复键、错误 UTF-8、非对象请求及异常 Unicode 标题。
- 校验 HTTP 状态码、响应字段与 SQLite 落库结果，输出 JSON/HTML 报告。

## 技术栈

Python 3.10+ 标准库：unittest、urllib、http.server、sqlite3、JSON，无第三方依赖。

## 快速开始

```powershell
git clone https://github.com/lu-13-debug/customer-ticket-api-tests.git
cd customer-ticket-api-tests
python run_tests.py
```

测试器自动启动本机动态端口服务，发送真实 HTTP 请求，结束后关闭服务器、线程与数据库连接，删除测试数据库。测试之间清理演示数据，同一工作目录使用固定测试数据库文件名，运行时避免同时启动两份测试进程。

只使用原生 unittest：`python -m unittest test_api -v`。

```powershell
# 手动启动 API
python server.py --port 8000
```

演示账号为 `alice / demo123`、`bob / demo123`，服务默认绑定 `127.0.0.1`。

## 接口契约

| 方法 / 路径 | 功能 | 主要检查 |
|---|---|---|
| POST /login | 登录并返回 token | 200 / 401，错误 JSON 为 400 |
| POST /tickets | 创建 open 工单 | 201，标题与 owner 落库一致 |
| GET /tickets | 当前账号工单分页 | total、排序、非法分页参数 400 |
| GET /tickets/{id} | 工单详情 | 他人工单 403，不存在 404 |
| PATCH /tickets/{id} | 更新状态 | 非法状态流转 409，权限与落库一致 |

除登录外需 `Authorization: Bearer <token>`。标题去首尾空白后为 1—100 字符，拒绝 NUL 和孤立 Unicode 代理字符；page 为 1—1,000,000，page_size 为 1—100，按 id 升序返回。JSON 仅接受对象，拒绝重复键和 NaN/Infinity。

## 测试范围与结果

15 条方法覆盖登录令牌、错误凭据、未授权访问、创建落库、标题边界、分页、状态流转、跨账号隔离、错误 JSON 与 SQL 注入样式文本。已补充未知账号且缺失密码、异常 Unicode 标题等回归子场景；非法输入返回 401/400 且不新增记录。

默认执行结果为 15 条真实 HTTP 测试通过。[JSON 结果](https://github.com/lu-13-debug/customer-ticket-api-tests/blob/main/reports/results.json) 与 [HTML 报告](https://github.com/lu-13-debug/customer-ticket-api-tests/blob/main/reports/results.html) 包含执行时间、逐条耗时、结果及异常堆栈；测试失败时返回非零退出码。

## 文件结构

```text
server.py           HTTP 路由、业务规则和 SQLite 存储
test_api.py         15 条测试方法与参数子场景
run_tests.py        运行测试并导出报告
reports/            results.json、results.html
```
