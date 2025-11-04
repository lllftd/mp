<script setup>
import { onMounted, reactive, ref } from "vue";
import { login, update_user_info } from "@/api";
import { setCache } from "@/utils/token.ts";

// 登录按钮类型
const value = ref(false);
const type = ref(0);
/**
 * 同意登录协议
 */
const changeRead = (flag) => {
  value.value = flag;
}

/**
 * 未设置同意登录的按钮点击事件
 */
const getPhoneClick = () => {
  if (!value.value) {
    uni.showToast({
      title: '请阅读并同意相关条例及协议',
      icon: "none"
    });
    return;
  }
}

// 返回上一页
const goback = () => {
  uni.navigateBack()
}
/**
 * 微信登录
 * @param code
 */
const wxLogin = () => {
  uni.login({
    provider: 'weixin',
    success: ({ code }) => {
      console.log('code=', code);
      login({
        code
      }).then((res) => {
        console.log(res.data.token);
        // // 调用更新用户信息接口
        const currentTime = new Date().getTime();
        const expirationTime = currentTime + 14 * 24 * 60 * 60 * 1000; // 两周后过期
        setCache('token', res.data.token, expirationTime);
        uni.setStorageSync('userInfo', res.data.user);
        uni.showToast({ title: "登录成功", icon: "none" });
        if (!res.data.user.phone && !res.data.user.avatar) {
          // 如果用户没有头像和用户昵称，则是第一次登录，更改用户的个人信息内容
          changeUserInfo()
          setTimeout(() => {
            uni.reLaunch({
              url: '/packages/choose_tag/index'
            })
          }, 1000)
        } else {
          setTimeout(() => {
            uni.reLaunch({
              url: '/pages/index/index'
            })
          }, 1000)
        }
        // }
      }).catch((error) => {
        console.error('登录失败:', error);
      });
    },
    fail(err) {
      console.log(err);
    }
  });

}

const changeUserInfo = () => {
  update_user_info({
    // 当前时间戳
    nickName: "用户" + Math.floor(Date.now() / 1000),
    avatar: "https://cdn.dxgr.org.cn/175705528917713061_avatar_1757055294.png",
  }).then((res) => {
    console.log(res);
  }).catch((error) => {
    console.error('修改失败:', error);
  });
}


const openPrivacyContract = () => {
  uni.openPrivacyContract({
    success: res => {
      console.log("openPrivacyContract success");
    },
    fail: res => {
      console.error("openPrivacyContract fail", res);
    },
  });
}

const goIndex = () => {
  uni.switchTab({
    url: '/pages/index/index'
  })
}
/**
 * 已选中同意按钮的点击事件
 * @param e
 */
// const getPhone = (e) => {
//   wxLogin();
// }
onMounted(() => {
  if (!type.value) {
    wxLogin();
  }
});

onLoad((options) => {
  type.value = options.type
})
</script>

<template>
  <view class="page-container">
    <!-- <img class="back-icon" @click="goback()" src="../../static/images/svgIcon/back.svg" alt=""> -->
    <img class="bg" src="../../static/images/bg2.png" alt="">

    <view class="page-content flex flex-column flex-y-center" v-if="type">
      <!-- <image class="logo" src="https://cdn.dxgr.org.cn/175507683897456712_logo_1755076843.png" alt="" /> -->
      <div class="login-btn" v-if="!value" @click="getPhoneClick">微信授权登录</div>
      <div class="login-btn" v-else @click="wxLogin">微信授权登录</div>
      <div class="login-btn cancel-btn" @click="goIndex">
        暂不登录
      </div>
      <div class="read flex flex-y-center">
        <div class="btn-group">
          <img @click="changeRead(true)" v-if="!value" class="check-icon"
            src="../../static/images/svgIcon/check-icon.svg" alt="">
          <img @click="changeRead(false)" v-else class="check-icon" src="../../static/images/svgIcon/check-icon-a.svg"
            alt="">
        </div>
        <div class="text" style="margin-left: 4rpx;">
          我已同意<text href="#" style="color: #2b85e4" @click="openPrivacyContract">《用户隐私保护协议》</text>
        </div>
      </div>
    </view>
  </view>
</template>

<style scoped lang="scss">
.page-container {
  position: relative;
  height: 100vh;
  background: #f3faed;

  .back-icon {
    width: 40rpx;
    height: 40rpx;
    position: fixed;
    top: 100rpx;
    left: 24rpx;
    z-index: 999;
  }

  .bg {
    width: 100%;
    height: 100%;
    position: absolute;
    z-index: 0;
    top: 0;
    left: 0;
  }

  .btn-group {
    .check-icon {
      width: 28rpx;
      height: 28rpx;
      padding: 20rpx;
      margin-top: 10rpx;
    }
  }

  .page-content {
    position: relative;
    z-index: 1;
    padding: 660rpx 58rpx 0;

    .logo {
      width: 456rpx;
      height: 684rpx;
    }

    .login-btn {
      width: 648rpx;
      height: 96rpx;
      line-height: 96rpx;
      text-align: center;
      font-size: 28rpx;
      background: #006241;
      color: #fff;
      border-radius: 16rpx;
    }

    .cancel-btn {
      margin-top: 40rpx;
      background: rgba(0, 0, 0, 0.74) !important;
    }

    .read {
      justify-content: flex-start;
      font-size: 26rpx;
      margin-top: 44rpx;
    }
  }
}
</style>
