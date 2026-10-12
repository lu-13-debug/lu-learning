"""运行真实 HTTP 测试并把实际结果保存为 JSON / HTML。"""
import html
import json
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

CASES = [
    "登录成功与会话令牌唯一性", "错误凭据返回 401", "未登录与伪造令牌返回 401",
    "创建工单与 SQL 落库一致", "标题长度 1 / 100 边界", "空白、超长与非字符串标题",
    "列表分页顺序与总数", "非法及重复分页参数", "合法状态流转及 SQL 持久化",
    "非法状态跳转不修改数据", "已解决工单不能重新打开", "工单及接口不存在返回 404",
    "不同账号工单访问与修改隔离", "错误 JSON、重复键及非对象请求", "SQL 注入样式文本安全落库",
]


class ReportResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
        self.started = {}
        self.statuses = {}

    def startTest(self, test):
        super().startTest(test)
        self.started[test.id()] = time.perf_counter()
        self.statuses[test.id()] = "通过"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.statuses[test.id()] = "失败"

    def addError(self, test, err):
        super().addError(test, err)
        self.statuses[test.id()] = "错误"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.statuses[test.id()] = "失败"

    def stopTest(self, test):
        key = test.id()
        self.cases.append({"id": key, "name": CASES[len(self.cases)],
                           "status": self.statuses[key],
                           "elapsed_seconds": round(time.perf_counter() - self.started[key], 4)})
        super().stopTest(test)


def main():
    base = Path(__file__).resolve().parent
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    start = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(str(base), pattern="test_api.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=ReportResult).run(suite)
    report = {"project": "客户工单管理接口测试", "scope": "2026.10 个人学习实践；本地演示被测服务",
              "started_at": started_at, "transport": "真实 HTTP / 127.0.0.1 动态端口 / urllib 无代理",
              "tests_run": result.testsRun,
              "passed": sum(case["status"] == "通过" for case in result.cases),
              "failures": len(result.failures), "errors": len(result.errors),
              "status": "通过" if result.wasSuccessful() else "失败",
              "elapsed_seconds": round(time.perf_counter() - start, 4), "cases": result.cases,
              "diagnostics": [{"id": test.id(), "traceback": traceback}
                              for test, traceback in result.failures + result.errors]}
    output = base / "reports"
    output.mkdir(exist_ok=True)
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join(f"<tr><td>{i:02}</td><td>{html.escape(case['name'])}</td>"
                   f"<td>{case['status']}</td><td>{case['elapsed_seconds']:.4f}s</td></tr>"
                   for i, case in enumerate(report["cases"], 1))
    diagnostics = "".join("<pre>" + html.escape(item["traceback"]) + "</pre>" for item in report["diagnostics"])
    document = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>客户工单管理接口测试报告</title><style>
body{{font-family:'Microsoft YaHei',sans-serif;background:#f3f6fa;color:#16273b;margin:0}}
main{{max-width:960px;margin:48px auto;padding:32px;background:white;border-radius:16px}}
.label{{color:#48729b;font-size:14px}}h1{{font-size:28px;margin:12px 0}}p{{line-height:1.7;color:#52647a}}
.cards{{display:flex;gap:16px;margin:28px 0}}.card{{flex:1;background:#edf5fa;padding:20px;border-radius:10px}}
.card b{{display:block;font-size:28px;color:#16705b}}table{{width:100%;border-collapse:collapse}}
th,td{{padding:12px;text-align:left;border-bottom:1px solid #e5ebf2;font-size:14px}}th{{background:#f5f8fb}}
pre{{white-space:pre-wrap;background:#fff0ef;padding:16px}}footer{{margin-top:24px;color:#66778a;font-size:12px}}
@media(max-width:650px){{main{{margin:12px;padding:20px}}.cards{{flex-wrap:wrap}}.card{{min-width:100px}}}}
</style><main><div class="label">个人学习实践 · 2026.10 · PYTHON 标准库</div>
<h1>客户工单管理接口测试</h1><p>本地演示服务的真实 HTTP 集成测试，覆盖登录、工单流转、权限隔离及数据库一致性。</p>
<div class="cards"><div class="card">执行用例<b>{report['tests_run']}</b></div>
<div class="card">通过<b>{report['passed']}</b></div><div class="card">失败 / 错误<b>{report['failures']} / {report['errors']}</b></div>
<div class="card">总体结果<b>{report['status']}</b></div></div>
<table><thead><tr><th>编号</th><th>测试案例</th><th>结果</th><th>耗时</th></tr></thead><tbody>{rows}</tbody></table>
{diagnostics}<footer>实际执行时间：{html.escape(started_at)} · 总耗时 {report['elapsed_seconds']}s<br>
被测对象为个人编写的本地练习 API；结果不代表企业系统质量、生产环境表现或完整安全审计。</footer></main></html>"""
    (output / "results.html").write_text(document, encoding="utf-8")
    print(f"报告已写入：{output}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
