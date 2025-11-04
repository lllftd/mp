<script setup>
import { onMounted, ref } from 'vue'
import { get_user_activity } from '@/api'
const user_activity = ref([])
const getUserActivity = async () => {
  const res = await get_user_activity()
  user_activity.value = res.data
}
const goDetail = (item) => {
    uni.navigateTo({
        url: `/packages/activity_detail/index?item=${JSON.stringify(item)}`
    });
}
onMounted(() => {
  getUserActivity()
})
</script>

<template>
  <div>
    <div class="container">
      <div v-if="user_activity.length > 0" class="content">
        <div class="list">
          <div @click="goDetail(item)" class="list-item flex" v-for="item in user_activity">
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
      </div>
      <div v-else class="nodata flex flex-column flex-x-center flex-y-center">
        <img class="no-data" src="../../static/images/no-data.png" alt="">
        <div class="text">您还没有参与任何活动哦～</div>
      </div>
    </div>
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100%;
  background: #fff;

  .list {
    padding: 28rpx 24rpx;
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
