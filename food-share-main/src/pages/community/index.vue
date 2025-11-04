<script setup>
import CusTabBar from "@/components/CusTabBar";
import { get_tweet_types, get_tweets, tweet_like_collect } from "@/api"
import { ref, onMounted } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { getAreasOf, getCitiesOf, getProvinces } from "@/constant/location_service.ts"
const currentNav = ref(0);
const defaultIndex = ref([0, 0, 0]);
// 帖子详情
const goDetail = (id) => {
  uni.navigateTo({
    url: `/packages/food_detail/index?id=${id}`
  });
}

// 前往搜索
const goSearch = () => {
  uni.navigateTo({
    url: '/packages/search/index'
  });
}

const currentCity = ref(null);
const tweetsLocationCode = ref(null);
const show = ref(false);
//初始省级数据
const provinceList = getProvinces();
// 初始市级数据
const cities = getCitiesOf(provinceList[0].code);
// 初始区数据
const areas = getAreasOf(cities[0].code);

// 地址选择数据列表
const columns = reactive([provinceList, cities, areas]);
// 地址选择组件
const uPickerRef = ref();

/**
 * 选中时执行
 * @param e
 */
const changeHandler = (e) => {
  const { columnIndex, value } = e;

  if (columnIndex === 0) {
    const cities = getCitiesOf(value[0].code);
    const areas = cities.length ? getAreasOf(cities[0].code) : [];

    // ✅ 同步更新 columns 和 uPicker
    columns[1] = cities;
    columns[2] = areas;

    uPickerRef.value.setColumnValues(1, cities);
    uPickerRef.value.setColumnValues(2, areas);

  } else if (columnIndex === 1) {
    const areas = getAreasOf(value[1].code); // ✅ 用当前选中的市

    // ✅ 同步更新
    columns[2] = areas;
    uPickerRef.value.setColumnValues(2, areas);
  }
};

/**
 * 单击确认按钮时执行
 * @param e
 */
const confirm = (e) => {
  // 输出数组 [省, 市, 区]
  const { value } = e;
  console.log(value);

  tweetsLocationCode.value = value[2].code;
  page.value = 1;
  tweetList.value = [];
  getTweetList()
  const inputV = value.map(item => item.label);

  currentCity.value = inputV.join();
  // 隐藏城市选择器
  show.value = false;
};

/**
 * 打开地址选择框&回显
 */
const showSelect = () => {
  show.value = true;

  if (currentCity.value) {
    const info = currentCity.value.split(',');
    let provinceIndex = 0;
    let cityIndex = 0;
    let areaIndex = 0;

    const province = provinceList.find(pro => pro.value === info[0]);
    if (province) {
      provinceIndex = provinceList.indexOf(province);
    }

    const cities = getCitiesOf(province.code);
    const city = cities.find(c => c.value === info[1]);
    if (city) {
      cityIndex = cities.indexOf(city);
    }

    const areas = getAreasOf(city.code);
    const area = areas.find(a => a.value === info[2]);
    if (area) {
      areaIndex = areas.indexOf(area);
    }

    // ✅ 同步更新 columns
    columns[1] = cities;
    columns[2] = areas;

    // ✅ 更新 uPicker 显示
    nextTick(() => {
      uPickerRef.value?.setColumnValues(1, cities);
      uPickerRef.value?.setColumnValues(2, areas);
    });

    defaultIndex.value = [provinceIndex, cityIndex, areaIndex];
  }
};

const resetPicker = () => {
  currentCity.value = null;
  tweetsLocationCode.value = null;

  // 重置 columns
  const p = provinceList[0];
  const c = getCitiesOf(p.code);
  const a = getAreasOf(c[0].code);

  columns[1] = c;
  columns[2] = a;

  defaultIndex.value = [0, 0, 0];

  nextTick(() => {
    uPickerRef.value?.setColumnValues(0, provinceList);
    uPickerRef.value?.setColumnValues(1, c);
    uPickerRef.value?.setColumnValues(2, a);
  });

  page.value = 1;
  tweetList.value = [];
  getTweetList();

  show.value = false;
};

// 获取推文分类
const tweetTypes = ref([]);
const getTweetTypes = async () => {
  const res = await get_tweet_types();
  tweetTypes.value = res.data;
  console.log(tweetTypes.value);

  currentNav.value = tweetTypes.value[0].id;
  getTweetList()
}

// 获取推文列表
const tweetList = ref([]);
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

const getTweetList = async () => {
  const res = await get_tweets({
    page: page.value,
    pageSize: pageSize.value,
    tweetsLocationCode: tweetsLocationCode.value,
    type: 'Hot'
  });
  const tweets = res.data.rows;
  total.value = res.data.total;
  pages.value = res.data.pages;

  const newTweets = tweets.map(item => {
    // 根据用户名生成固定头像
    const avatar = avatars[hashString(item.tweetsUser) % avatars.length];

    return {
      ...item,
      avatar // 固定头像
    };
  });

  tweetList.value = [...tweetList.value, ...newTweets];
};

// 点赞收藏操作
const tweetActions = async (id, type, isflag) => {
  // 先找到要操作的 item
  const item = tweetList.value.find(t => t.id === id);
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
      tweetsRecordId,
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

onMounted(() => {
  getTweetTypes();
});

onShow(() => {
  // page.value = 1;
  // tweetList.value = [];
  // getTweetList();
});

let page = ref(1)
let pageSize = ref(10)
let pages = ref(0)
const total = ref(null);
onReachBottom(() => {
  console.log(page.value, pages.value);
  if (page.value < pages.value) {
    page.value++
    getTweetList()
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
      <div class="header flex">
        <div class="choose-city flex flex-y-center" @click="showSelect">
          {{ currentCity || '选择城市' }}
          <img class="select-icon" src="../../static/images/svgIcon/filter-icon.svg" alt="">
        </div>
        <div class="search" @click="goSearch">
          <img class="search-icon" src="../../static/images/svgIcon/search.svg" alt="">
        </div>
      </div>
      <div class="content">
        <scroll-view scroll-x="true" style="width: 100vw; background: #fff;">
          <div class="nav flex">
            <div @click="currentNav = item.id" v-for="item in tweetTypes" :key="item.id" class="nav-item"
              :class="{ 'active': currentNav == item.id }">{{ item.name }}</div>
          </div>
        </scroll-view>
        <div class="list" v-if="tweetList.length">
          <div class="list-item" v-for="item in tweetList" :key="item.id" @click="goDetail(item.id)">
            <div class="user-info flex flex-y-center">
              <img class="avatar" :src="item.avatar" alt="">
              <div class="name">{{ item.tweetsUser }}</div>
            </div>
            <div class="cover-img">
              <img class="bg" :src="JSON.parse(item.tweetsImg)[0]" alt="">
              <div class="tags flex flex-y-center">
                <div v-for="tag in item.typeCidNames.split(',')" class="tag">{{ tag }}</div>
              </div>
            </div>
            <div class="bot-actions flex flex-y-center flex-x-between">
              <div class="title">
                {{ item.tweetsTitle }}
              </div>
              <div class="actions flex flex-y-center">
                <!-- <div class="btn flex flex-y-center">
                  <img class="icon" src="../../static/images/svgIcon/evalute.svg" alt="">{{ item.browseNum }}
                </div> -->
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
        <div v-else class="no-data flex flex-column flex-x-center flex-y-center">
          <img class="no-data-icon" src="../../static/images/svgIcon/no-data.svg" alt="">
          <div class="text">暂无数据</div>
        </div>

      </div>
      <up-picker :show="show" ref="uPickerRef" :columns="columns" @confirm="confirm" @change="changeHandler"
        :defaultIndex="defaultIndex" @cancel="resetPicker" keyName="label">

      </up-picker>
    </div>
    <CusTabBar />
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100%;
  background: #fff;

  .header {
    width: 100%;
    padding: 100rpx 20rpx 10rpx;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    font-size: 28rpx;
    position: fixed;
    top: 0;
    left: 0;
    z-index: 99;
    background: #fff;

    .choose-city {
      padding: 12rpx 24rpx;
      border-radius: 32rpx;
      border: 1px solid #F0F0F0;

      .select-icon {
        width: 20rpx;
        height: 16rpx;
        margin-left: 12rpx;
      }
    }

    .search {
      width: 64rpx;
      height: 64rpx;
      border-radius: 50%;
      margin-left: 20rpx;

      .search-icon {
        width: 100%;
        height: 100%;
      }
    }
  }

  .content {
    .nav {
      min-width: 100vw;
      padding: 24rpx 34rpx;
      box-sizing: border-box;
      position: fixed;
      top: 174rpx;
      left: 0;
      background: #fff;
      z-index: 99;

      .nav-item {
        width: fit-content;
        white-space: nowrap;
        margin-right: 64rpx;
        font-size: 26rpx;
        color: #868484;
        position: relative;
      }

      .active {
        color: #006241;
        font-weight: 600;

        &::after {
          content: "";
          position: absolute;
          bottom: -6rpx;
          left: 3rpx;
          width: 20rpx;
          height: 4rpx;
          background: #006241;
        }
      }
    }

    .list {
      padding-top: 270rpx;
      padding-bottom: 180rpx;

      .list-item {
        .user-info {
          padding: 0rpx 34rpx 16rpx;

          .avatar {
            width: 32rpx;
            height: 32rpx;
            border-radius: 50%;
            margin-right: 12rpx;
          }

          .name {
            font-size: 24rpx;
            line-height: 48rpx;
            letter-spacing: 2%;
          }
        }

        .cover-img {
          width: 100%;
          height: 562rpx;
          position: relative;

          .bg {
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
          }

          .tags {
            position: absolute;
            bottom: 18rpx;
            left: 32rpx;
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

          .title {
            font-size: 30rpx;
            font-weight: 500;
            width: 460rpx;
            white-space: nowrap;
            text-overflow: ellipsis;
            overflow: hidden;
          }

          .btn {
            width: 90rpx;
            height: 60rpx;
            margin-right: 24rpx;
            font-size: 28rpx;

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
              width: 60rpx;
              height: 60rpx;
            }
          }
        }
      }
    }
  }

  .no-data {
    height: 80vh;

    .no-data-icon {
      width: 320rpx;
      height: 320rpx;
    }

    .text {
      font-size: 28rpx;
      color: #868484;
      margin-top: 40rpx;
    }
  }
}
</style>
