<template>
  <image src="https://dz-detection.oss-cn-beijing.aliyuncs.com/admin_3/1701411556214login-bg.png" class="bg"
    mode="heightFix" />
  <!-- <button class="login-btn" @click="getUserProfile" data-eventsync="true">一键登录</button> -->
  <!-- <button class="login-btn" type="default" open-type="getPhoneNumber" @getphonenumber="decryptPhoneNumber">获取手机号</button> -->
</template>

<script setup>
import { wx_xcx_login, dy_xcx_login } from "@/api/index";
// const decryptPhoneNumber = (e)=>{
//   console.log(111,e);
// }
uni.login({
  success({ code }) {
    wx_xcx_login({ js_code: code, shop_id: uni.getStorageSync("shop_id") }).then((response) => {
      uni.showToast({ title: "登录成功", icon: "none" });
      uni.setStorageSync("token", response.info.token);
      setTimeout(() => {
        uni.reLaunch({
          url: '/pages/index/index'
        })
      }, 1500)

    })
  },
  fail(err) {
    console.log(err);
  }
});
const getUserProfile = () => {
  // #ifdef MP-WEIXIN
  uni.showModal({
    title: "温馨提示",
    content: "亲，授权微信登录后才能正常使用小程序功能",
    success({ confirm }) {
      confirm &&
        uni.getUserProfile({
          desc: "用于完善会员资料",
          success({ encryptedData, iv }) {

          },
          fail(err) {
            console.log(err);
          }
        })
    }
  })
  // #endif
  // #ifdef MP-TOUTIAO
  uni.getUserProfile({
    desc: "用于完善会员资料",
    success({ encryptedData, iv }) {
      console.log("uni.getUserProfile")
      uni.login({
        success({ code }) {
          console.log("uni.login")
          dy_xcx_login({ encryptedData, iv, js_code: code, shop_id: uni.getStorageSync("shop_id"), is_test: 1 }).then((response) => {
            uni.showToast({ title: "登录成功", icon: "none" });
            uni.setStorageSync("token", response.info.token);
            setTimeout(() => {
              uni.reLaunch({
                url: '/pages/index/index'
              })
            }, 1500)
          })
        },
        fail(err) {
          console.log(err);
        }
      });
    },
    fail(err) {
      console.log(err);
    }
  })
  // #endif
}
</script>

<style scoped lang="scss">
.bg {
  position: absolute;
  right: 0;
  height: 100vh;
  overflow: hidden;
  background-size: contain;
  z-index: 1;
}

.login-btn {
  position: absolute;
  top: 1223rpx;
  left: 57rpx;
  width: 640rpx;
  height: 88rpx;
  border-radius: 48rpx;
  background: #000000;

  font-family: PingFangSC;
  font-size: 32rpx;
  font-weight: normal;
  line-height: 88rpx;
  text-align: center;
  letter-spacing: 0rpx;

  color: #ffffff;
  z-index: 9;
}

.tables {
  position: absolute;
  width: 90%;
  z-index: 999;
  display: flex;
  top: 30%;
  left: 12%;
  flex-wrap: wrap;

  .table {
    width: 171rpx;
    height: 65rpx;
    border-radius: 10rpx;
    background: #FFFFFF;
    box-shadow: 0rpx 4rpx 10rpx 0rpx rgba(0, 0, 0, 0.302);
    color: #000;
    font-size: 24rpx;
    line-height: 65rpx;
    text-align: center;
    margin: 20rpx 40rpx 20rpx 0;
  }

  .table-c {
    background-color: red;
    color: #fff;
  }
}
</style>