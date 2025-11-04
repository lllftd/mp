bindPickerChange
<script setup>
import { ref } from "vue";
import { get_activity_list, get_tweets, tweet_like_collect } from "@/api";
const searchList = ref([]);
const keyword = ref("");
const array = ['活动', '推文']
const currentIndex = ref(0)
const avatars = [
  "https://js.njhanqian.tech/share/1ce63172c35747769753838278643718.jpg", // 狗
  "https://js.njhanqian.tech/share/5133c13c30414529b4277f9cf31c1e9b.jpg", // 狗2
  "https://js.njhanqian.tech/share/b39c69c616f64a33aa1a267cfd8f5644.jpg", // 牛
  "https://js.njhanqian.tech/share/57088e2a6a394e91b65da9d0565679a7.jpg", // 鱼
  "https://js.njhanqian.tech/share/3aecdc3ad2604008aa8585943cbb3a70.jpg", // 人
  "https://js.njhanqian.tech/share/26071767a5ea445e9a9994068112ad8c.jpg", // 动漫人
  "https://js.njhanqian.tech/share/69f2db51e1fb4e069227ca0a24dd4326.png", // 蔡徐坤
  "https://js.njhanqian.tech/share/b2196783818a42419165cb59ca5f5d69.jpg", // 歪嘴小猫
];

// 工具函数：字符串转哈希整数
function hashString(str) {
  let hash = 0;
  if (str?.length === 0) return hash;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char; // 简单哈希算法
    hash |= 0; // 转为32位整数
  }
  return Math.abs(hash); // 返回正整数
}
const bindPickerChange = (e) => {
  currentIndex.value = e.detail.value;
  page.value = 1;
  searchList.value = [];
}
const fetchSearchList = async () => {
  console.log(currentIndex.value, keyword.value);
  
  if (currentIndex.value == 0) {
    const res = await get_activity_list({
      page: page.value,
      pageSize: pageSize.value,
      actTitle: keyword.value
    });
    if (res.code === 200) {
      searchList.value = [...searchList.value, ...res.data.rows];
      total.value = res.data.total;
      pages.value = res.data.totalPage;
    }
  } else {
    const res = await get_tweets({
      page: page.value,
      pageSize: pageSize.value,
      keywords: keyword.value
    });
    if (res.code === 200) {
      const tweets = res.data.rows;
      total.value = res.data.total;
      pages.value = res.data.totalPage;
      const newTweets = tweets.map(item => {
        // 根据用户名生成固定头像
        const avatar = avatars[hashString(item.tweetsUser) % avatars.length];

        return {
          ...item,
          avatar // 固定头像
        };
      });
      searchList.value = [...searchList.value, ...newTweets];
    }
  }
}

const tweetActions = async (id, type, isflag) => {

  // 先找到要操作的 item
  const item = searchList.value.find(t => t.id === id);
  if (!item) return;

  // 更新本地状态
  if (type === 'like') {
    item.userStatus.like = !item.userStatus.like;
    item.likeNum += item.userStatus.like ? 1 : -1;
  } else if (type === 'collect') {
    item.userStatus.collect = !item.userStatus.collect;
    item.collectNum += item.userStatus.collect ? 1 : -1;
  }

  // 获取 recordId
  const tweetsRecordId = type === 'like'
    ? item.userStatus.likeRecordId
    : item.userStatus.collectRecordId;

  try {
    // ✅ 发起请求（确保 tweet_like_collect 返回 Promise）
    const res = await tweet_like_collect({
      type,
      tweetsId: id,
      tweetsRecordId: isflag ? tweetsRecordId : '',
      flag: !isflag ? 'add' : ''
    });

    // 请求成功再提示
    uni.showToast({
      title: type === 'like'
        ? (item.userStatus.like ? '点赞成功' : '取消点赞')
        : (item.userStatus.collect ? '收藏成功' : '取消收藏'),
      icon: 'none',
      duration: 1000
    });

  } catch (error) {
    // 如果失败，回滚状态
    if (type === 'like') {
      item.userStatus.like = !item.userStatus.like;
      item.likeNum += item.userStatus.like ? 1 : -1;
    } else if (type === 'collect') {
      item.userStatus.collect = !item.userStatus.collect;
      item.collectNum += item.userStatus.collect ? 1 : -1;
    }

    uni.showToast({
      title: '操作失败，请重试',
      icon: 'none',
      duration: 1000
    });
  }
}

const goDetail = (item) => {
  uni.navigateTo({
    url: `/packages/activity_detail/index?item=${JSON.stringify(item)}`
  });
}
const goDetail2 = (id) => {
  uni.navigateTo({
    url: `/packages/food_detail/index?id=${id}`
  });
}

const goBack = () => {
  uni.navigateBack();
}

let page = ref(1)
let pageSize = ref(10)
let pages = ref(0)
const total = ref(null);
onReachBottom(() => {
  console.log(page.value, pages.value);
  if (page.value < pages.value) {
    page.value++
    getCollectList()
  } else {
    uni.showToast({
      title: '已经到底了哦',
      icon: 'none',
      duration: 1000
    })
  }
})
</script>

<template>
  <div>
    <div class="container">
      <div class="header">
        <div class="search-input flex flex-y-center flex-x-between">
          <div class="input-box flex flex-y-center">
            <picker @change="bindPickerChange" :value="currentIndex" :range="array">
              <div class="left-wrap flex flex-y-center">
                <div class="text">{{ array[currentIndex] }} <img class="select-icon"
                    src="../../static/images/svgIcon/select-2.svg" alt=""> |
                </div>
                <img class="search-icon" src="../../static/images/svgIcon/search2.svg" alt="">
              </div>
            </picker>
            <input v-model="keyword" @confirm="fetchSearchList" class="input" type="text" placeholder="请输入关键词搜索"
              placeholder-class="my-placeholder" />
          </div>
          <div class="button" @click="goBack">取消</div>
        </div>
      </div>
      <div v-if="searchList.length > 0" class="content">
        <div v-if="currentIndex == 0" class="list">
          <div @click="goDetail(item)" class="list-item flex" v-for="item in searchList">
            <img class="cover" :src="item.actImg" alt="">
            <div class="box flex flex-column">
              <div>
                <div class="title">{{ item.actTitle }}</div>
                <div class="desc">{{ item.actDescribe }}</div>
              </div>
              <div class="time flex flex-y-center">
                <img class="time-icon" src="../../static/images/svgIcon/time.svg" alt="">
                {{ item.actStartDate }} - {{ item.actEndDate }}
              </div>
            </div>
          </div>
        </div>
        <div v-else class="list2 flex flex-wrap flex-x-between">
          <div class="list-item" v-for="item in searchList" @click="goDetail2(item.id)">
            <div class="cover-img">
              <img class="bg" :src="JSON.parse(item.tweetsImg)[0]" alt="">
              <div class="tags flex flex-y-center">
                <div v-for="tag in item.typeCidNames.split(',')" class="tag">{{ tag }}</div>
              </div>
            </div>
            <div class="bot-actions">
              <div class="title">
                {{ item.tweetsTitle }}
              </div>
              <div class="bot flex flex-y-center flex-x-between">
                <div class="user flex flex-y-center">
                  <img class="avatar" :src="item.avatar" alt="">
                  <div class="name">{{ item.tweetsUser }}</div>
                </div>
                <div class="actions flex flex-y-center">
                  <div @click.stop="tweetActions(item.id, 'collect', item.userStatus.collect)"
                    class="btn flex flex-y-center">
                    <img class="icon2"
                      :src="item.userStatus.collect ? '../../static/images/svgIcon/collect-a.svg' : '../../static/images/svgIcon/collect2.svg'"
                      alt="">{{ item.collectNum }}
                  </div>
                  <div @click.stop="tweetActions(item.id, 'like', item.userStatus.like)" class="btn flex flex-y-center">
                    <img class="icon3"
                      :src="item.userStatus.like ? '../../static/images/svgIcon/like-a.svg' : '../../static/images/svgIcon/like2.svg'"
                      alt="">{{ item.likeNum }}
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
      <div v-else class="nodata flex flex-column flex-x-center flex-y-center">
        <img class="no-data" src="../../static/images/no-data.png" alt="">
        <div class="text">当前暂无搜索结果~</div>
      </div>

    </div>
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100%;
  background: #fff;

  .header {
    width: 100%;
    background: #fff;
    padding: 34rpx 24rpx 10rpx;
    position: fixed;
    z-index: 99;
    font-size: 24rpx;

    .left-wrap {
      position: absolute;
      left: 50rpx;
      top: 52rpx;
      cursor: pointer;

      .select-icon {
        width: 18rpx;
        height: 18rpx;
        padding: 0 10rpx;
      }

      .search-icon {
        width: 24rpx;
        height: 24rpx;
        padding-left: 14rpx;
      }
    }

    .input {
      width: 604rpx;
      height: 72rpx;
      background: #f8f8f8;
      border-radius: 36rpx;
      padding-left: 180rpx;
      box-sizing: border-box;
    }

    :deep(.my-placeholder) {
      font-size: 24rpx;
      color: #999999;
    }
  }


  .list2 {
    padding: 30rpx 10rpx 180rpx;

    .list-item {

      .cover-img {
        width: 360rpx;
        height: 466rpx;
        position: relative;
        border-radius: 16rpx 16rpx 0 0;

        .bg {
          position: absolute;
          width: 100%;
          height: 100%;
          border-radius: 16rpx 16rpx 0 0;
          top: 0;
          left: 0;
        }

        .tags {
          position: absolute;
          bottom: 18rpx;
          left: 16rpx;
          font-size: 20rpx;
          color: #fff;

          .tag {
            background: rgba(0, 0, 0, 0.74);
            border-radius: 8rpx;
            padding: 4rpx 9rpx;
            margin-right: 14rpx;
          }
        }
      }


      .bot-actions {
        padding: 24rpx;

        .bot {
          .user {
            .name {
              font-size: 24rpx;
            }
            .avatar {
              width: 32rpx;
              height: 32rpx;
              border-radius: 50%;
              margin-right: 12rpx;
            }
          }

        }

        .title {
          width: 320rpx;

          font-size: 30rpx;
          font-weight: 500;
        }

        .btn {
          width: 80rpx;
          height: 60rpx;
          margin-right: 14rpx;

          &:nth-child(2) {
            margin-right: 18rpx;
          }

          &:last-child {
            margin-right: 0;
          }

          .icon {
            width: 40rpx;
            height: 40rpx;
            margin-right: 10rpx;
          }

          .icon2 {
            width: 32rpx;
            height: 32rpx;
            margin-right: 10rpx;
          }

          .icon3 {
            width: 48rpx;
            height: 48rpx;
          }
        }
      }

    }
  }

  .list {
    padding: 132rpx 24rpx 28rpx;
    border-top: 1rpx solid #EBEBEB;

    .list-item {
      margin-bottom: 32rpx;

      .cover {
        width: 208rpx;
        height: 208rpx;
        margin-right: 20rpx;
      }

      .box {
        padding: 10rpx 0;
        justify-content: space-between;

        .title {
          font-size: 30rpx;
          font-weight: 500;
          margin-bottom: 10rpx;
        }

        .desc {
          font-size: 24rpx;
          color: rgba(0, 0, 0, 0.47);
        }

        .time {
          .time-icon {
            width: 28rpx;
            height: 28rpx;
            margin-right: 10rpx;
          }

          font-size: 24rpx;
          color: #6F6F6F;
        }
      }
    }
  }

  .nodata {
    height: 60vh;

    .no-data {
      width: 260rpx;
      height: 200rpx;
      margin-bottom: 44rpx;
    }

    .text {
      font-size: 28rpx;
      color: #5A577F;
    }
  }
}
</style>
