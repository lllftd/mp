<script setup>
import CusTabBar from "@/components/CusTabBar";
import { ref, onMounted, reactive } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { logout, update_user_info, imgUpload, get_user_info, get_tweet_browse_records } from "@/api";
import { showToast } from "../../utils/tools";
const is_login = ref(false);
const userId = ref(null);
const mineData = reactive({
  like: 0,
  collect: 0,
  view: 0,
})
const userInfo = ref(null);
const goDetail = (url) => {
  uni.navigateTo({ url });
}
const handleClick = () => {
  if (!is_login.value) {
    uni.navigateTo({ url: `/pages/login/index?type=${1}` });
  } else {
    return;
  }
}
const getNumbers = async () => {
  try {
    const [likeRes, collectRes, browseRes] = await Promise.all([
      get_tweet_browse_records({ page: 1, pageSize: 999, type: 'like' }),
      get_tweet_browse_records({ page: 1, pageSize: 999, type: 'collect' }),
      get_tweet_browse_records({ page: 1, pageSize: 999, type: 'browse' })
    ]);

    mineData.like = likeRes.data.total;
    mineData.collect = collectRes.data.total;
    mineData.view = browseRes.data.total; // 注意：你原代码是 browse，但 mineData 是 view，这里修正
  } catch (error) {
    console.error('获取数据失败:', error);
  }
};

function onChooseAvatar(e) {

  const { avatarUrl } = e.detail; // 头像临时路径
  console.log("头像临时路径:", avatarUrl);
  if (avatarUrl) {
    imgUpload(avatarUrl)
      .then(url => {
        console.log(url);
        userInfo.value.avatar = url;
        update_user_info({ avatar: url }).then(() => {
          console.log("更新成功");
          // getUserInfo()
          // uni.setStorageSync('userInfo', userInfo.value);
        }).catch(() => {
          console.log("更新失败");
        });

      })
      .catch(() => { });
  }
}

function onGetNickname(res) {
  console.log('【昵称授权回调】', res);
  if (res.detail?.nickName) {
    const nickName = res.detail.nickName;
    userInfo.value.nickName = nickName;
    // 更新本地 userInfo
    uni.setStorageSync('userInfo', {
      ...userInfo.value,
      nickName
    });

    update_user_info({ nickName }).then(() => {
      console.log("更新成功");
    })
  } else {
    uni.showToast({ title: '昵称授权失败', icon: 'none' });
  }
}

const getUserInfo = () => {
  get_user_info({
    id: userId.value
  }).then(res => {
    userInfo.value = res.data;
  })
}

const handleLogout = () => {
  logout().then(() => {
    uni.removeStorageSync('token');
    uni.removeStorageSync('userInfo');
    is_login.value = false;
    userInfo.value = null;
  });
}
onShow(() => {
  is_login.value = uni.getStorageSync('token').value;
  userId.value = uni.getStorageSync('userInfo').id;
  getUserInfo()
  getNumbers()
});
</script>

<template>
  <div>
    <div class="container">
      <div class="header flex flex-x-center">
        我的
      </div>
      <div class="content">
        <div class="user-info flex flex-x-between">
          <div class="flex flex-y-center">
            <button v-if="is_login" class="avatar-wrapper btn" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
              <img class="avatar" :src="is_login ? userInfo.avatar : '../../static/images/avatar-nologin.png'" alt="">
            </button>
            <button v-else class="avatar-wrapper btn">
              <img class="avatar" :src="is_login ? userInfo.avatar : '../../static/images/avatar-nologin.png'" alt="">
            </button>
            <div class="info">
              <button v-if="is_login" class="name-btn" open-type="nickname" @getuserinfo="onGetNickname"
                style="background: transparent; border: none; padding: 0; font-size: 32rpx; font-weight: 500;">
                <text class="name">{{ userInfo.nickName }}</text>
              </button>
              <div v-else @click="handleClick" class="name">点击登录</div>
              <div class="tip flex flex-y-center">{{ is_login ? '欢迎使用本小程序' : ' 登陆更精彩' }} <img class="right-icon"
                  src="../../static/images/svgIcon/right-icon.svg" alt=""></div>
            </div>
          </div>
          <div class="notice flex flex-y-center" @click="goDetail('/packages/my_notice/index')">消息通知<img
              class="notice-icon" src="../../static/images/svgIcon/notice.svg" alt=""></div>
        </div>
        <div class="order" :class="{ 'is-login': is_login }">
          <div class="title">详细数据</div>
          <div class="bot-number flex flex-x-between">
            <div class="item" @click="goDetail('/packages/my_like/index')">
              <div class="num">{{ is_login? mineData.like : 0 }}</div>
              <div class="name flex flex-y-center flex-x-between">我喜欢的 <img class="icon"
                  :src="is_login ? '../../static/images/svgIcon/like-a.svg' : '../../static/images/svgIcon/like2.svg'"
                  alt=""></div>
            </div>
            <div class="item" @click="goDetail('/packages/my_collect/index')">
              <div class="num">{{ is_login? mineData.collect : 0 }}</div>
              <div class="name flex flex-y-center flex-x-between">我的收藏 <img class="icon2"
                  :src="is_login ? '../../static/images/svgIcon/collect-a.svg' : '../../static/images/svgIcon/collect2.svg'"
                  alt=""></div>
            </div>
            <div class="item" @click="goDetail('/packages/my_history/index')">
              <div class="num">{{ is_login? mineData.view : 0 }}</div>
              <div class="name flex flex-y-center flex-x-between">历史浏览 <img class="icon3"
                  :src="is_login ? '../../static/images/svgIcon/view-a.svg' : '../../static/images/svgIcon/view.svg'"
                  alt=""></div>
            </div>
          </div>
        </div>
        <div class="active">
          <div class="title">我参与的活动</div>
          <div class="active-box flex flex-x-between">
            <div @click="goDetail('/packages/my_activity/index')" class="active-item flex flex-column">
              <div class="name">参与的活动</div>
              <div class="tip">Activities participated in</div>
            </div>
            <div @click="goDetail('/packages/choose_tag/index')" class="active-item flex flex-column">
              <div class="name">兴趣标签</div>
              <div class="tip">interest tags</div>
            </div>
          </div>
        </div>
      </div>
      <div @click="handleLogout" v-show="is_login" class="login-out">退出登录</div>
    </div>
    <CusTabBar />
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100%;
  background: linear-gradient(180.02deg, #FFFFFF 32.95%, #F5F5F5 71.54%, #F5F5F5 99.98%);


  .header {
    padding: 90rpx 20rpx 20rpx;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    font-size: 34rpx;
    font-weight: 500;
  }

  .content {
    padding: 30rpx;
    box-sizing: border-box;

    .user-info {
      margin-bottom: 34rpx;
      align-items: flex-start;

      .name-btn {
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        height: 85rpx;

        &::after {
          content: "";
          border: none;
        }
      }

      .avatar-wrapper {
        // 去除button默认样式
        height: 128rpx;
        background: none;
        border: none;
        padding: 0;
        margin: 0;

        &::after {
          content: "";
          border: none;
        }

        .avatar {
          width: 128rpx;
          height: 128rpx;
          border-radius: 50%;
          margin-right: 16rpx;
        }
      }

      .name {
        font-size: 32rpx;
        font-weight: 500;
        margin-bottom: 20rpx;
      }

      .tip {
        font-size: 24rpx;
        color: #A9A9A9;

        .right-icon {
          width: 18rpx;
          height: 18rpx;
          padding-left: 6rpx;
        }
      }

      .notice {
        padding-top: 18rpx;
        font-size: 28rpx;
        color: rgba(0, 0, 0, 0.37);

        .notice-icon {
          width: 48rpx;
          height: 48rpx;
        }
      }
    }

    .order {
      padding: 22rpx 16rpx;
      background: #FAFAFA;
      margin-bottom: 54rpx;
      border-radius: 8rpx;

      .title {
        font-size: 28rpx;
        font-weight: 500;
        margin-bottom: 12rpx;
      }

      .bot-number {
        .item {
          width: 30%;
          background: #fff;
          padding: 48rpx 16rpx 16rpx;
          border-radius: 8rpx;

          .name {
            height: 50rpx;
            font-size: 24rpx;
            color: rgba(0, 0, 0, 0.41);
          }

          .icon {
            width: 42rpx;
            height: 42rpx;
          }

          .icon2 {
            width: 28rpx;
            height: 28rpx;
          }

          .icon3 {
            width: 44rpx;
            height: 44rpx;
          }
        }
      }
    }

    .is-login {
      position: relative;
      background: #006241 !important;

      .title {
        color: #fff !important;
      }

      &::after {
        content: "";
        position: absolute;
        background: url('../../static/images/bg.png') no-repeat;
        background-size: 100% 100%;
        width: 192rpx;
        height: 100rpx;
        right: 0;
        top: -64rpx;
      }
    }

    .active {
      .title {
        font-size: 24rpx;
        margin-bottom: 28rpx;
      }

      .active-item {
        width: 340rpx;
        height: 186rpx;
        border-radius: 16rpx;
        color: #fff;
        padding: 14rpx;
        box-sizing: border-box;
        justify-content: flex-end;

        .name {
          font-size: 28rpx;
        }

        .tip {
          color: rgba(255, 255, 255, 0.45);
          font-size: 20rpx;
        }

        &:first-child {
          background: url('../../static/images/mine01.png') no-repeat;
          background-size: 100% 100%;
        }

        &:last-child {
          background: url('../../static/images/mine02.png') no-repeat;
          background-size: 100% 100%;
        }
      }
    }
  }

  .login-out {
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: 220rpx;
    width: 92%;
    height: 96rpx;
    border-radius: 8rpx;
    text-align: center;
    line-height: 96rpx;
    font-size: 28rpx;
    border: 1px solid #006241;
    background: #fff;
  }

}
</style>
