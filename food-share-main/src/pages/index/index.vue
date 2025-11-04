<script setup>
import CusTabBar from "@/components/CusTabBar";
import { ref, onMounted } from "vue";
import { get_rand_tweets, tweet_like_collect, get_tweet_is_like_collect } from "@/api"
import { getAreasOf, getCitiesOf, getProvinces } from "@/constant/location_service.ts"
const currentCity = ref(null);
const tweetsLocationCode = ref(null);
// 前往搜索
const goSearch = () => {
  uni.navigateTo({
    url: '/packages/search/index'
  });
}

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
const defaultIndex = ref([0, 0, 0]);
const changeHandler = (e) => {
  const { columnIndex, index, indexs, value, values } = e;

  if (columnIndex === 0) { // 选择第一列数据时
    // 设置第二列关联数据
    const cities = getCitiesOf(value[columnIndex].code);
    uPickerRef.value.setColumnValues(1, cities);

    const area = getAreasOf(cities[0].code);
    // 设置第三列关联数据
    uPickerRef.value.setColumnValues(2, area);

  } else if (columnIndex === 1) {
    const area = getAreasOf(value[1].code);
    uPickerRef.value.setColumnValues(2, area);
  }
}

/**
 * 单击确认按钮时执行
 * @param e
 */
const confirm = (e) => {
  // 输出数组 [省, 市, 区]
  const { value } = e;
  // tweetsLocationCode.value = value[2].code;
  // getTweets()
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
    let province = { provinceIndex: 0, info: {} };
    let city = { cityIndex: 0, info: {} };
    let areaObj = { areaIndex: 0, info: {} };

    if (info[0]) {
      province.provinceIndex = provinceList.findIndex(pro => pro.value === info[0]);
      province.info = provinceList.find(pro => pro.value === info[0])
    }

    if (info[1]) {
      const cityList = getCitiesOf(province.info.code);
      uPickerRef.value.setColumnValues(1, cityList);
      city.cityIndex = cityList.findIndex(city => city.value === info[1]);
      city.info = cityList.find(city => city.value === info[1]);

      if (info[2]) {
        const areaList = getAreasOf(city.info.code);
        uPickerRef.value.setColumnValues(2, areaList);
        areaObj.areaIndex = areaList.findIndex(are => are.value === info[2]);
        areaObj.info = areaList.find(are => are.value === info[2]);
      }
    }

    defaultIndex.value = [province.provinceIndex, city.cityIndex, areaObj.areaIndex];
  }

}


const hearts = ref([]);
let heartId = 0;

const handleLike = () => {
  const newHeart = {
    id: heartId++,
    style: {
      left: '65%', // 居中
      animationDelay: '0s'
    }
  };
  hearts.value.push(newHeart);

  // 动画结束后自动移除
  setTimeout(() => {
    removeHeart(hearts.value.findIndex(h => h.id === newHeart.id));
  }, 1000);
};
const removeHeart = (index) => {
  if (index !== -1) {
    hearts.value.splice(index, 1);
  }
};

const sadFaces = ref([]);
let sadId = 0;
const handleDislike = () => {
  const newSad = {
    id: sadId++,
    style: {
      left: '28%',
      animationDelay: '0s'
    }
  };
  sadFaces.value.push(newSad);

  // 动画结束后自动移除
  setTimeout(() => {
    removeSadFace(sadFaces.value.findIndex(s => s.id === newSad.id));
  }, 1800);
};

const removeSadFace = (index) => {
  if (index !== -1) {
    sadFaces.value.splice(index, 1);
  }
};


// 获取随机推文
const tweetList = ref([]);
const getTweets = async () => {
  const res = await get_rand_tweets({ 
    searchTypeKeyword: '美食',
    // tweetsLocationCode: tweetsLocationCode.value
  });
  const tweets = res.data;
  // 并发获取每条推文的点赞/收藏状态
  const statusPromises = tweets.map(async (tweet) => {
    try {
      const res = await get_tweet_is_like_collect({
        tweetsId: tweet.id  // 每次传一个 ID
      });
      // 返回 { id, like, collect }
      return {
        id: tweet.id,
        likeRecordId: res.data?.likeRecordId ?? 0,
        collectRecordId: res.data?.collectRecordId ?? 0,
        isLike: res.data?.like ?? false,
        isCollect: res.data?.collect ?? false
      };
    } catch (error) {
      console.error(`获取推文 ${tweet.id} 状态失败`, error);
    }
  });

  // 等待所有状态请求完成
  const statusResults = await Promise.all(statusPromises);

  // 构建状态映射表
  const statusMap = {};
  statusResults.forEach(item => {
    statusMap[item.id] = {
      isLike: item.isLike,
      isCollect: item.isCollect,
      likeRecordId: item.likeRecordId,
      collectRecordId: item.collectRecordId
    };
  });

  // 合并所有数据，赋值给 tweetList
  tweetList.value = tweets.map(tweet => ({
    ...tweet,
    isLike: statusMap[tweet.id]?.isLike ?? false,
    isCollect: statusMap[tweet.id]?.isCollect ?? false,
    likeRecordId: statusMap[tweet.id]?.likeRecordId ?? 0,
    collectRecordId: statusMap[tweet.id]?.collectRecordId ?? 0,
  }));

  console.log("最终 tweetList", tweetList.value);
}

// 点赞收藏操作
const tweetActions = async (id, type, isflag) => {
  // 找到当前项
  const currentItem = tweetList.value.find(item => item.id === id);
  if (!currentItem) return;

  // === 1. 乐观更新 UI ===
  if (type === 'like') {
    currentItem.isLike = !currentItem.isLike;
    handleLike();
  } else if (type === 'collect') {
    currentItem.isCollect = !currentItem.isCollect;
  }

  // === 2. 发送请求 ===
  try {
    const recordId = type === 'like' ? currentItem.likeRecordId : currentItem.collectRecordId;
    const res = await tweet_like_collect({
      type,
      tweetsId: id,
      tweetsRecordId: recordId,
      flag: isflag ? 'remove' : 'add'  // 注意逻辑：当前是已点赞 → 点击即取消
    });

    if (res.code === 200) {
      // ✅ 请求成功：更新 recordId（只更新 ID，不重拉状态）
      if (type === 'like') {
        currentItem.likeRecordId = res.data?.likeRecordId || 0;
      } else if (type === 'collect') {
        currentItem.collectRecordId = res.data?.collectRecordId || 0;
      }

      // 可选：提示
      if (type === 'collect') {
        uni.showToast({
          title: isflag ? '取消收藏' : '收藏成功',
          icon: 'none',
          duration: 1500
        });
      }
    }
  } catch (error) {
    console.error('操作失败', error);
    // === 回滚 UI ===
    if (type === 'like') {
      currentItem.isLike = !currentItem.isLike;
    } else if (type === 'collect') {
      currentItem.isCollect = !currentItem.isCollect;
    }
    uni.showToast({
      title: '网络错误，请重试',
      icon: 'none',
      duration: 2000
    });
  }
};
// 帖子详情
const goDetail = (id) => {
  uni.navigateTo({
    url: "/packages/food_detail/index?id=" + id
  });
}


const currentIndex = ref(0)
const modelType = ref(null)

// 解析图片数组
const parseImg = (imgStr) => {
  try {
    return JSON.parse(imgStr)
  } catch (e) {
    return [imgStr]
  }
}

// 当前卡片样式（包含位移和旋转）
const touch = ref({ startX: 0, moveX: 0, moved: false })
const transition = ref('transform 0.3s ease')
const displayCards = computed(() => {
  const list = tweetList.value;
  const idx = currentIndex.value;
  return [
    list[idx],
    list[idx + 1], // 下一张
    list[idx + 1]  // 再下一张
  ].filter(Boolean); // 防止越界
});

const getCardStyle = (stackIndex, item) => {
  const dx = touch.value.moveX;
  const maxRotate = 15;
  const rotate = Math.max(-maxRotate, Math.min(maxRotate, (dx / 100) * 15));
  const opacity = 1 - Math.min(Math.abs(dx) / 300, 0.5);

  // 层级控制：当前卡片在最上，后面的依次降低
  const zIndex = displayCards.value.length - stackIndex;

  // 后面的卡片：缩小、透明、带阴影
  if (stackIndex === 0) {
    // 当前卡片（可拖动）
    return {
      transform: `translateX(${dx}px) rotate(${rotate}deg) scale(1)`,
      transition: transition.value,
      opacity: opacity.toString(),
      zIndex: zIndex,
      boxShadow: '0 20rpx 60rpx rgba(0,0,0,0.2)'
    };
  } else {
    const scale = 1 - (stackIndex * 0.08); // 每后一张缩小 8%
    const yShift = stackIndex * 40; // 向下偏移
    return {
      transform: `scale(${scale}) translateY(${yShift}rpx)`,
      transition: 'transform 0.4s ease, opacity 0.4s ease',
      opacity: '0.9',
      zIndex: zIndex,
      boxShadow: '0 10rpx 40rpx rgba(0,0,0,0.1)'
    };
  }
};

// Touch 开始
const handleTouchStart = (e) => {
  touch.value.startX = e.touches[0].clientX
  touch.value.moved = false
}

// Touch 移动
const handleTouchMove = (e) => {
  modelType.value = 'like'
  const moveX = e.touches[0].clientX - touch.value.startX
  touch.value.moveX = moveX
  touch.value.moved = true
}

// Touch 结束
const handleTouchEnd = () => {
  const dx = touch.value.moveX
  const threshold = 100 // 滑动判定阈值

  transition.value = 'transform 0.5s ease'

  if (dx > threshold) {
    // 右滑 → 喜欢
    touch.value.moveX = 300
    setTimeout(nextCard, 300)
    emitAction('like')
  } else if (dx < -threshold) {
    // 左滑 → 不喜欢
    touch.value.moveX = -300
    setTimeout(nextCard, 300)
    emitAction('dislike')
  } else {
    // 回弹
    touch.value.moveX = 0
    transition.value = 'transform 0.3s ease'
  }
  touch.value.moved = false
}

// 下一张卡片
const nextCard = () => {
  if (currentIndex.value >= tweetList.value.length - 2) {
    currentIndex.value = 0;
    getTweets()
  }
  currentIndex.value++;
  // 重置手势
  touch.value.moveX = 0;
  transition.value = 'transform 0.3s ease';
};

// 手动点击左滑
const swipeLeft = () => {
  touch.value.moveX = -300
  transition.value = 'transform 0.5s ease'
  setTimeout(nextCard, 300)
  emitAction('dislike')

}

// 手动点击右滑
const swipeRight = () => {
  touch.value.moveX = 300
  transition.value = 'transform 0.5s ease'
  setTimeout(nextCard, 300)
  emitAction('like')
}

// 触发喜欢/不喜欢事件
const emitAction = (type) => {
  console.log('Action:', type, 'Item:', tweetList.value[currentIndex.value])
  const item = tweetList.value[currentIndex.value]
  if (type === 'like') {
    tweetActions(item.id, 'like', item.isLike)
    handleLike();
  } else if (type === 'dislike') {
    handleDislike();
  }
}

onMounted(() => {
  getTweets();
});
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
      <div class="card">
        <view class="cards-stack">
          <view v-for="(item, index) in displayCards" :key="item.id" class="card-item"
            :style="getCardStyle(index, item)" @touchstart="index === 0 ? handleTouchStart($event) : null"
            @touchmove="index === 0 ? handleTouchMove($event) : null"
            @touchend="index === 0 ? handleTouchEnd($event) : null" @click="index === 0 ? goDetail(item.id) : null">
            <view class="slide-content">
              <image class="food-img" :src="parseImg(item.tweetsImg)[0]" mode="aspectFill" />
              <view class="tags flex">
                <view class="tag" v-for="tag in item.typeCidNames.split(',')" :key="tag">{{ tag }}</view>
              </view>
              <view class="info">
                <view class="food-title">{{ item.tweetsTitle }}</view>
                <view class="local">{{ item.tweetsDescribe }}</view>
              </view>
              <view class="mask" v-if="index === 0 && touch.moved"
                :class="{ 'left': touch.moveX < 0, 'right': touch.moveX > 0 }">
                <text class="mask-icon">{{ touch.moveX < 0 ? '❌' : '❤' }}</text>
              </view>
            </view>
          </view>
          <div class="heart-container">
            <div v-for="(heart, index) in hearts" :key="index" class="heart" :style="heart.style"
              @animationend="removeHeart(index)">❤</div>
          </div>
          <div class="sad-container">
            <div v-for="(sad, index) in sadFaces" :key="index" class="sad-face" :style="sad.style"
              @animationend="removeSadFace(index)">😔</div>
          </div>
        </view>
        <div class="actions flex">
          <div @click.stop="swipeLeft" class="btn flex flex-x-center flex-y-center">
            <img class="icon" src="../../static/images/svgIcon/close.svg" alt="">
          </div>
          <div @click.stop="tweetActions(tweetList[currentIndex]?.id, 'collect', tweetList[currentIndex].isCollect)"
            class="btn flex flex-x-center flex-y-center">
            <div style="display: none;">{{ tweetList[currentIndex]?.isCollect }}</div>
            <img class="icon2"
              :src="tweetList[currentIndex]?.isCollect ? '../../static/images/svgIcon/collect-a.svg' : '../../static/images/svgIcon/collect.svg'"
              alt="">
          </div>
          <div @click.stop="swipeRight()" class="btn flex flex-x-center flex-y-center">
            <img class="icon3" src="../../static/images/svgIcon/like.svg" alt="">
          </div>
        </div>
      </div>
      <up-picker :show="show" ref="uPickerRef" :columns="columns" @confirm="confirm" @change="changeHandler"
        :defaultIndex="defaultIndex" @cancel="show = false" keyName="label">

      </up-picker>
    </div>
    <CusTabBar />
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100vh;
  background: #fff;

  .header {
    padding: 100rpx 20rpx 10rpx;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    font-size: 28rpx;
    margin-bottom: 46rpx;

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

  .card {
    position: relative;
    width: 100%;
    overflow: visible;
    padding: 0;
    box-sizing: border-box;
    border-radius: 20px;

    &::after {
      content: "";
      display: block;
      position: absolute;
      width: 100%;
      height: 1180rpx;
      background: #d2daef;
      border-radius: 20px;
      left: 50%;
      transform: translateX(-50%) scale(0.9); 
      transition: all 0.3s ease;
      bottom: -80rpx;
    }

    .cards-stack {
      position: relative;
      width: 100%;
      height: 1180rpx;
      justify-content: center;

      .heart-container {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 999;

        .heart {
          position: absolute;
          bottom: 300rpx;
          transform: none;
          opacity: 0;
          pointer-events: none;
          animation: floatUp 1s ease-out forwards;
          font-size: 40rpx; // 控制表情大小
          color: #ff471e;
        }

        @keyframes floatUp {
          0% {
            transform: translate(-50%, 240rpx) rotate(0deg) scale(0);
            opacity: 0;
          }

          10% {
            opacity: 0.5;
          }

          50% {
            transform: translate(-50%, 240rpx) rotate(15deg) scale(1.2);
            opacity: 1;
          }

          100% {
            transform: translate(-50%, 60rpx) rotate(30deg) scale(1.8);
            opacity: 0;
          }
        }
      }

      .sad-container {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 999;

        .sad-face {
          position: absolute;
          bottom: 300rpx;
          transform: none;
          opacity: 0;
          pointer-events: none;
          animation: floatUpSad 1s ease-out forwards;
          font-size: 40rpx; // 控制表情大小
        }
      }

      @keyframes floatUpSad {
        0% {
          transform: translate(-50%, 240rpx) rotate(0deg) scale(0);
          opacity: 0;
        }

        10% {
          opacity: 0.5;
        }

        50% {
          transform: translate(-50%, 240rpx) rotate(-15deg) scale(1.2);
          opacity: 1;
        }

        100% {
          transform: translate(-50%, 60rpx) rotate(-30deg) scale(1.8);
          opacity: 0;
        }
      }
    }

    .mask {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      display: flex;
      justify-content: center;
      align-items: center;
      pointer-events: none; // 允许穿透点击
      z-index: 10;
      background: rgba(0, 0, 0, 0.7);

      .mask-icon {
        font-size: 120rpx;
        opacity: 0.9;
        transform: scale(0);
        animation: appear 0.1s forwards;
      }

      &.left .mask-icon {
        color: #999;
      }

      &.right .mask-icon {
        color: #ff471e;
      }

      @keyframes appear {
        from {
          transform: scale(0);
        }

        to {
          transform: scale(1);
        }
      }
    }

    .card-item {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 100%;
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.1);
      background: #006241;
      color: #fff;
      backface-visibility: hidden;
    }

    .slide-content {
      position: relative;
      width: 100%;
      height: 100%;
    }

    .food-img {
      width: 100%;
      height: 970rpx;
      object-fit: cover;
      background: #ccc;
    }

    .tags {
      position: absolute;
      top: 915rpx;
      left: 28rpx;

      .tag {
        padding: 2rpx 8rpx;
        border-radius: 4rpx;
        background: rgba(60, 62, 69, 0.65);
        color: #fff;
        font-size: 20rpx;
        font-weight: 400;
        margin-right: 15rpx;
      }
    }

    .info {
      padding: 20rpx 28rpx;
    }

    .food-title {
      width: 660rpx;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 32rpx;
      font-weight: bold;
    }

    .local {
      font-size: 28rpx;
      margin-top: 15rpx;
      color: rgba(255, 255, 255, 0.79);
      line-height: 100%;
      letter-spacing: 2%;
    }

    .actions {
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      margin-top: -60rpx;
      z-index: 10;

      .btn {
        width: 96rpx;
        height: 96rpx;
        margin: 0 6rpx;
        border-radius: 50%;
        background: #fff;

        .icon {
          width: 32rpx;
          height: 32rpx;
        }

        .icon2 {
          width: 40rpx;
          height: 40rpx;
        }

        .icon3 {
          width: 48rpx;
          height: 42rpx;
        }

        &:nth-child(3) {
          border-radius: 48rpx;
          width: 180rpx;
          background: #FF471E;

          &:hover {
            background: #ff471e;
            transform: scale(1.1);
            animation: shake 0.5s ease-in-out;

            .icon3 {
              filter: brightness(0) invert(1);
            }
          }
        }

        @keyframes shake {
          0% {
            transform: scale(1.1) rotate(0deg);
          }

          25% {
            transform: scale(1.05) rotate(5deg);
          }

          50% {
            transform: scale(1.1) rotate(-5deg);
          }

          75% {
            transform: scale(1.05) rotate(3deg);
          }

          100% {
            transform: scale(1) rotate(0deg);
          }
        }
      }
    }
  }



}
</style>
