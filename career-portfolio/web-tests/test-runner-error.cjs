// 回归：基础设施失败必须覆盖旧通过报告，不能留下上次全通过的误导性结果。
const {spawnSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const result=spawnSync(process.execPath,[path.join(__dirname,'run.cjs')],{
  cwd:root,env:{...process.env,PLAYWRIGHT_CHANNEL:'intentionally-invalid-channel'},encoding:'utf8',windowsHide:true,
});
assert.notEqual(result.status,0);
const report=JSON.parse(fs.readFileSync(path.join(root,'reports/web/results.json'),'utf8'));
assert.equal(report.status,'infrastructure_error');
assert.ok(report.fatal_error.includes('intentionally-invalid-channel'));
assert.equal(report.passed,0);
console.log('PASS 基础设施失败覆盖历史通过报告');
