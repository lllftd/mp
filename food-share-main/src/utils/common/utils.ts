import { onLoad, onShow } from "@dcloudio/uni-app";
import { getUserInfoApi } from "../../api/modular/user";
import {
  ref
} from "vue";
export function core() {
  /**
   * 店铺ID
   * @type {ComputedRef<T>}
   */
  const shopId = ref(uni.getStorageSync("shop_id"))
  const updateShopId = () => {
    shopId.value = uni.getStorageSync("shop_id")
  }
  // 用户基本信息
  const userDetail = ref(uni.getStorageSync("userInfo"));

  const updateUserDetail = () => {
    userDetail.value = uni.getStorageSync("userInfo")
  }
  /*onLoad(() => {
    if (!userDetail.value) {
      getUserDetail()
    }
  })
  */
  // 更新店铺信息

  /**
   * 查询店铺基本信息
   */
  const getShopInfo = () => {
    shopInfo({ shop_id: shopId.value }).then((res) => {
      if (res.code === 200) {
        uni.setStorageSync('shopinfo', res.info)
      } else {
        uni.showToast({
          title: res.msg,
          icon: "none"
        })
      }
    }).catch((err) => {
      console.log(err);
    })
  }

  /**
   * 获取用户基本信息,如需修改用户信息调用次函数即可，会同步更新缓存
   */
  const getUserDetail = () => {
    console.log("保存用户信息")
    getUserInfoApi({ shop_id: shopId.value }).then((res: any) => {
      if (res.code === 200) {
        uni.setStorageSync("userInfo", res.info);
        userDetail.value = res.info;
      } else {
        uni.showToast({
          title: res.msg,
          icon: 'none',
        })
      }
    }).catch((err: any) => {
      console.log(err);
    })
  }

  /**
   * 格式化金额，保留两位小数
   * @param moeny
   */
  const moneyFormat = (money: any) => {
    if (money === 0 || !money) {
      return '0.00';
    }
    return (money / 100).toFixed(2);
  }

  return {
    getUserDetail,
    shopId,
    userDetail,
    getShopInfo,
    updateUserDetail,
    moneyFormat,
    updateShopId
  }
}