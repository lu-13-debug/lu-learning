const {chromium} = require('playwright');
const {spawn,execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {ShopPage} = require('./pages.cjs');
const {cases} = require('./cases.cjs');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'reports','web');
const python=process.env.PYTHON_BIN || (process.platform==='win32'?'python':'python3');
const port=Number(process.env.SHOP_PORT || 0);
let baseURL;
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const health=url=>new Promise((resolve,reject)=>{const req=http.get(url,res=>{res.resume();resolve(res.statusCode);});req.setTimeout(1500,()=>req.destroy(new Error('health timeout')));req.on('error',reject);});
const state={started_at:new Date().toISOString(),browser:null,results:[]};
function saveReport(status,fatalError=null){
  fs.mkdirSync(out,{recursive:true});
  const results=state.results;
  const report={project:'电商Web页面自动化测试',data_source:'本地合成业务靶场',started_at:state.started_at,browser:state.browser,status,fatal_error:fatalError,total:results.length,passed:results.filter(x=>x.status==='passed').length,failed:results.filter(x=>x.status==='failed').length,results};
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(report,null,2));
  fs.writeFileSync(path.join(out,'index.html'),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Web自动化执行报告</title><style>body{font:15px/1.7 system-ui;max-width:1080px;margin:45px auto;color:#172b4d;padding:0 24px}h1{font-size:30px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #e2e8f0}.passed{color:#087b61}.failed{color:#b42318}pre{white-space:pre-wrap;background:#f1f5f9;padding:10px}</style><h1>电商 Web 自动化执行报告</h1><p>本地演示应用 · 独立上下文隔离 · 真实浏览器执行</p><p>本次状态：<b>${escape(status)}</b> · ${report.total} 条已执行 / ${report.passed} 通过 / ${report.failed} 失败<br>浏览器 ${escape(report.browser||'尚未启动')} · 执行时间 ${escape(report.started_at)}</p>${fatalError?`<h2>执行未完成</h2><pre>${escape(fatalError)}</pre>`:''}<table><tr><th>编号</th><th>验证场景</th><th>结果</th><th>耗时</th></tr>${results.map(r=>`<tr><td>${r.id}</td><td>${escape(r.name)}${r.error?`<details><summary>错误与定位</summary><pre>${escape(r.error)}</pre><a href="${r.id}-failure.png">失败截图</a> · <a href="${r.id}-trace.zip">Trace</a></details>`:''}</td><td class="${r.status}">${r.status}</td><td>${r.duration_ms} ms</td></tr>`).join('')}</table><p>仅验证本项目列出的功能，不代表生产系统质量、安全性或全浏览器兼容性。</p></html>`);
  return report;
}

async function main(){
  fs.mkdirSync(out,{recursive:true}); fs.mkdirSync(path.join(root,'runtime'),{recursive:true});
  saveReport('running');
  const db=path.join(root,'runtime',`test-${Date.now()}-${process.pid}.db`);
  const server=spawn(python,['-m','webshop.app','--port',String(port),'--db',db],{cwd:root,stdio:['ignore','pipe','pipe'],windowsHide:true});
  let serverLog=''; server.stdout.on('data',x=>serverLog+=x); server.stderr.on('data',x=>serverLog+=x);
  let serverError; server.on('error',e=>{serverError=e;});
  let browser;
  const results=state.results;
  try {
    let ready=false; let lastHealthError='';
    for(let i=0;i<80;i++){
      if(serverError) throw serverError;
      if(server.exitCode!==null) throw new Error(`演示服务退出: ${serverLog}`);
      const match=serverLog.match(/Demo shop: (http:\/\/127\.0\.0\.1:\d+)/);if(match)baseURL=match[1];
      if(baseURL)try{const status=await health(`${baseURL}/health`); if(status===200){ready=true;break;} lastHealthError=`HTTP ${status}`;}catch(e){lastHealthError=e.message;}
      await sleep(100);
    }
    if(!ready) throw new Error(`服务未就绪: ${lastHealthError} / ${serverLog}`);
    const options={headless:true};
    if(process.env.PLAYWRIGHT_CHANNEL) options.channel=process.env.PLAYWRIGHT_CHANNEL;
    else if(process.platform==='win32') options.channel='msedge';
    browser=await chromium.launch(options);
    state.browser=await browser.version();
    const readOrder=id=>JSON.parse(execFileSync(python,['-c',
      'import json,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.row_factory=sqlite3.Row; r=dict(c.execute("SELECT total_cents FROM orders WHERE id=?",(int(sys.argv[2]),)).fetchone()); r.update(dict(c.execute("SELECT SUM(quantity*price_cents) AS items_total_cents,COUNT(*) AS item_count FROM order_items WHERE order_id=?",(int(sys.argv[2]),)).fetchone())); c.close(); print(json.dumps(r))',db,String(id)],{encoding:'utf8',windowsHide:true}));
    const filtered=cases.filter(([id])=>!process.env.TEST_FILTER||id.includes(process.env.TEST_FILTER));
    if(!filtered.length) throw new Error('筛选条件未匹配任何用例');
    for(const [id,name,run] of filtered){
      const context=await browser.newContext({viewport:{width:1365,height:900}});
      await context.tracing.start({screenshots:true,snapshots:true});
      const page=await context.newPage(); page.setDefaultTimeout(4000);
      const before=Date.now(); let error=null;
      try{const shop=new ShopPage(page,baseURL);await shop.open();await run({shop,page,browser,baseURL,readOrder});}
      catch(e){error=e.stack||String(e); await page.screenshot({path:path.join(out,`${id}-failure.png`),fullPage:true}).catch(()=>{});}
      await context.tracing.stop(error?{path:path.join(out,`${id}-trace.zip`)}:{});
      await context.close();
      results.push({id,name,status:error?'failed':'passed',duration_ms:Date.now()-before,error});
      console.log(`${error?'FAIL':'PASS'} ${id} ${name}`);
    }
    const page=await browser.newPage({viewport:{width:1365,height:900}});
    await page.goto(baseURL); await page.screenshot({path:path.join(out,'shop-preview.png'),fullPage:true}); await page.close();
    const report=saveReport(results.some(x=>x.status==='failed')?'failed':'passed');
    if(report.failed) process.exitCode=1;
  } finally {
    if(browser) await browser.close();
    server.kill();
  }
}
main().catch(e=>{console.error(e);saveReport('infrastructure_error',e.stack||String(e));process.exitCode=1;});
