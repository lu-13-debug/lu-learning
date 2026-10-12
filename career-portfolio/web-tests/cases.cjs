const assert = require('node:assert/strict');
const {ShopPage} = require('./pages.cjs');

async function text(page, content) { await page.getByText(content, {exact:true}).waitFor(); }
async function login(shop) { await shop.login(); await shop.loggedIn(); }
async function cartTotal(page, value) { await text(page, `合计 ¥${value}`); }

const cases = [
  ['WEB-01', '首页展示商品与学习项目标识', async ({page}) => {
    await page.getByRole('heading',{name:'好物商店',exact:true}).waitFor();
    await text(page,'本地学习靶场 · 无真实支付');
    await page.getByTestId('product-card').nth(3).waitFor();
    assert.equal(await page.getByTestId('product-card').count(),4);
  }],
  ['WEB-02', '正确账号登录成功', async ({shop,page}) => {
    await login(shop); await text(page,'登录成功');
  }],
  ['WEB-03', '错误密码明确提示且保持未登录', async ({shop,page}) => {
    await shop.login('demo','wrong'); await text(page,'用户名或密码错误');
    assert.equal(await page.getByRole('button',{name:'退出登录'}).count(),0);
  }],
  ['WEB-04', '空账号和密码被拦截', async ({shop,page}) => {
    await shop.login('',''); await text(page,'请输入用户名和密码');
  }],
  ['WEB-05', '搜索结果与关键字一致', async ({shop,page}) => {
    await shop.search('键盘'); await page.getByTestId('product-1').waitFor();
    assert.equal(await page.getByTestId('product-card').count(),1);
  }],
  ['WEB-06', '无匹配商品显示空状态', async ({shop,page}) => {
    await shop.search('不存在的商品'); await text(page,'未找到匹配商品');
  }],
  ['WEB-07', '未登录加入购物车提示登录', async ({shop,page}) => {
    await shop.add(1); await text(page,'请先登录');
  }],
  ['WEB-08', '加入商品后数量与金额一致', async ({shop,page}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    assert.equal(await shop.cartItem(1).getByLabel('商品数量').inputValue(),'1');
  }],
  ['WEB-09', '数量修改重新计算金额', async ({shop,page}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    await shop.cartItem(1).getByLabel('商品数量').fill('2');
    await shop.cartItem(1).getByRole('button',{name:'更新'}).click();
    await cartTotal(page,'258.00');
  }],
  ['WEB-10', '数量零被拒绝且购物车不变', async ({shop,page}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    await shop.cartItem(1).getByLabel('商品数量').fill('0');
    await shop.cartItem(1).getByRole('button',{name:'更新'}).click();
    await text(page,'数量必须是1到20之间的整数'); await cartTotal(page,'129.00');
  }],
  ['WEB-11', '数量超过上限被拒绝', async ({shop,page}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    await shop.cartItem(1).getByLabel('商品数量').fill('21');
    await shop.cartItem(1).getByRole('button',{name:'更新'}).click();
    await text(page,'数量必须是1到20之间的整数');
  }],
  ['WEB-12', '移除商品恢复空购物车', async ({shop,page}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    await shop.cartItem(1).getByRole('button',{name:'移除'}).click();
    await text(page,'购物车还是空的'); await cartTotal(page,'0.00');
  }],
  ['WEB-13', '售罄商品禁用加购按钮', async ({shop}) => {
    assert.equal(await shop.product(3).getByRole('button',{name:'加入购物车'}).isDisabled(),true);
  }],
  ['WEB-14', '空购物车下单显示错误', async ({shop,page}) => {
    await login(shop); await shop.checkout(); await text(page,'购物车为空');
  }],
  ['WEB-15', '收货地址过短被拒绝且保留商品', async ({shop,page}) => {
    await login(shop); await shop.add(2); await cartTotal(page,'59.00');
    await shop.checkout('深圳'); await text(page,'收货地址需填写8到200个字符');
    await cartTotal(page,'59.00');
  }],
  ['WEB-16', '购物到下单完整链路并核对SQLite落库', async ({shop,page,readOrder}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    await shop.add(2); await cartTotal(page,'188.00'); await shop.checkout();
    await page.getByTestId('order-success').waitFor();
    const id = Number(await page.getByTestId('order-success').getAttribute('data-order-id'));
    const row = readOrder(id);
    assert.equal(row.total_cents,18800); assert.equal(row.items_total_cents,18800);
    assert.equal(row.item_count,2); await text(page,'购物车还是空的');
    await text(page,`订单 #${id} · ¥188.00`);
  }],
  ['WEB-17', '退出登录后无法继续提交订单', async ({shop,page}) => {
    await login(shop); await page.getByRole('button',{name:'退出登录'}).click();
    await text(page,'已退出登录'); await shop.checkout(); await text(page,'请先登录');
  }],
  ['WEB-18', '独立浏览器上下文不共享购物车', async ({shop,page,browser,baseURL}) => {
    await login(shop); await shop.add(1); await cartTotal(page,'129.00');
    const other = await browser.newContext();
    try { const otherPage=await other.newPage(); const otherShop=new ShopPage(otherPage,baseURL);
      await otherShop.open(); await login(otherShop); await cartTotal(otherPage,'0.00');
      await text(otherPage,'购物车还是空的');
    } finally {await other.close();}
  }],
];
module.exports={cases};
