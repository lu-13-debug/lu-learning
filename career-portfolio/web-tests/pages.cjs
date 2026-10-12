class ShopPage {
  constructor(page, baseURL) { this.page = page; this.baseURL = baseURL; }
  async open() { await this.page.goto(this.baseURL); }
  async login(username='demo', password='Demo123!') {
    await this.page.getByLabel('用户名', {exact:true}).fill(username);
    await this.page.getByLabel('密码', {exact:true}).fill(password);
    await this.page.getByRole('button', {name:'登录', exact:true}).click();
  }
  async loggedIn() { await this.page.getByRole('button', {name:'退出登录'}).waitFor(); }
  product(id) { return this.page.getByTestId(`product-${id}`); }
  cartItem(id) { return this.page.getByTestId(`cart-${id}`); }
  async add(id) { await this.product(id).getByRole('button', {name:'加入购物车'}).click(); }
  async search(text) {
    await this.page.getByLabel('搜索商品').fill(text);
    await this.page.getByRole('button', {name:'搜索', exact:true}).click();
    await this.page.getByTestId('results-caption').filter({hasText:`搜索“${text}”`}).waitFor();
  }
  async checkout(address='深圳市测试街道123号') {
    await this.page.getByLabel('收货地址').fill(address);
    await this.page.getByRole('button', {name:'提交订单',exact:true}).click();
  }
}
module.exports = {ShopPage};
