//金额转换 分->元 保留2位小数 并每隔3位用逗号分开 1,234.56
export function abs(val) {
  let str = (val / 100).toFixed(2) + "";
  let intSum = str.substring(0, str.indexOf(".")).replace(/\B(?=(?:\d{3})+$)/g, ","); //取到整数部分
  let dot = str.substring(str.length, str.indexOf(".")); //取到小数部分搜索
  let ret = intSum + dot;
  ret.slice(-2) === "00" ? (ret = ret.slice(0, -3)) : ret;
  return ret;
}
