<script setup>
import { ref, onMounted } from "vue";
import { get_tweet_browse_records, get_tweet_is_like_collect, get_user_info } from "@/api";

const goDetail = (id) => {
  uni.navigateTo({
    url: "/packages/food_detail/index?id=" + id
  });
}

// 获取我的浏览列表
const browsetList = ref([]);

const getBrowseList = async () => {
  // 1. 获取推文列表
  const res = await get_tweet_browse_records({
    page: page.value,
    pageSize: pageSize.value,
    type: 'browse',
  });
  const tweets = res.data.rows;
  total.value = res.data.total;
  pages.value = res.data.totalPage;

  // 2. 并发获取每条推文的点赞/收藏状态
  const statusPromises = tweets.map(async (tweet) => {
    try {
      const res = await get_tweet_is_like_collect({
        tweetsId: tweet.id  // 每次传一个 ID
      });
      // 返回 { id, like, collect }
      return {
        id: tweet.id,
        isLike: res.data?.like ?? false,
        isCollect: res.data?.collect ?? false
      };
    } catch (error) {
      console.error(`获取推文 ${tweet.id} 状态失败`, error);
      return {
        id: tweet.id,
        isLike: false,
        isCollect: false
      };
    }
  });

  // 等待所有状态请求完成
  const statusResults = await Promise.all(statusPromises);

  // 构建状态映射表
  const statusMap = {};
  statusResults.forEach(item => {
    statusMap[item.id] = {
      isLike: item.isLike,
      isCollect: item.isCollect
    };
  });

  // 3. 获取用户信息（并发）
  const userIds = [...new Set(tweets.map(t => t.clientUserId))];
  console.log("userIds", userIds);

  const userMap = {};

  if (userIds.length > 0) {
    try {
      const userPromises = userIds.map(id => get_user_info({ id }));
      const userResponses = await Promise.all(userPromises);
      userResponses.forEach((res, index) => {
        if (res.data) {
          userMap[userIds[index]] = res.data;
          console.log("userMap", userMap);

        }
      });
    } catch (error) {
      console.error("获取用户信息失败", error);
    }
  }

  // 4. 合并所有数据，赋值给 tweetList
  const newBrowse = tweets.map(tweet => ({
    ...tweet,
    isLike: statusMap[tweet.id]?.isLike ?? false,
    isCollect: statusMap[tweet.id]?.isCollect ?? false,
    createUser: userMap[tweet.clientUserId] || {
      name: '未知用户',
      avatar: 'https://cdn.dxgr.org.cn/175705528917713061_avatar_1757055294.png'
    }
  }));
  browsetList.value = [...browsetList.value, ...newBrowse];
  console.log("最终 browsetList", browsetList.value);
};


onMounted(() => {
  getBrowseList()
})

let page = ref(1)
let pageSize = ref(10)
let pages = ref(0)
const total = ref(null);
onReachBottom(() => {
  console.log(page.value, pages.value);
  if (page.value < pages.value) {
    page.value++
    getBrowseList()
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
      <div class="content" v-if="browsetList.length > 0">
        <div class="list flex flex-wrap flex-x-between">
          <div class="list-item" v-for="item in browsetList" :key="item.id" @click="goDetail(item.tweetsId)">
            <div class="cover-img">
              <img class="bg" :src="JSON.parse(item.tweetsImg)[0]" alt="">
              <!-- <div class="tags flex flex-y-center">
                <div class="tag">人均50</div>
                <div class="tag">节假日</div>
                <div class="tag">节假日</div>
              </div> -->
            </div>
            <div class="bot-actions">
              <div class="title" style="margin-bottom: 10rpx;">
                {{ item.tweetsTitle }}
              </div>
              <div class="bot flex flex-y-center flex-x-between">
                <div class="user flex flex-y-center">
                  <img class="avatar" :src="item.createUser.avatar" alt="">
                  <div class="name">{{ item.createUser.nickName }}</div>
                </div>
                <!-- <div class="actions flex flex-y-center">
                  <div class="btn flex flex-y-center">
                    <img class="icon2" src="../../static/images/svgIcon/collect2.svg" alt="">10
                    <img class="icon2" src="../../static/images/svgIcon/collect-a.svg" alt="">10
                  </div>
                  <div class="btn flex flex-y-center">
                    <img class="icon3" src="../../static/images/svgIcon/like2.svg" alt="">25
                    <img class="icon3" src="../../static/images/svgIcon/like-a.svg" alt="">25
                  </div>
                </div> -->
              </div>
            </div>

          </div>
        </div>

      </div>
      <div v-else class="nodata flex flex-column flex-x-center flex-y-center">
        <img class="no-data" src="../../static/images/no-data.png" alt="">
        <div class="text">您还没有浏览任何美食哦～</div>
      </div>
    </div>
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100%;

  .content {
    background: #fbfbfb;

    .list {
      padding: 30rpx 10rpx 80rpx;

      .list-item {
        margin-bottom: 20rpx;
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
          padding: 12rpx;

          .bot {
            .user {
              .avatar {
                width: 32rpx;
                height: 32rpx;
                border-radius: 50%;
                margin-right: 12rpx;
              }

              .name {
                font-size: 24rpx;
                width: 220rpx;
                color: #5A577F;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
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
