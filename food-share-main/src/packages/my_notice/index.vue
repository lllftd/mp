<script setup>
import { onMounted, ref } from 'vue'
import { get_message_records } from '@/api'
const message_records = ref([])

const getMessage = async () => {
  const res = await get_message_records()
  message_records.value = res.data
}

onMounted(() => {
  getMessage()
})
</script>

<template>
  <div>
    <div class="container">
      <div class="content" v-if="message_records.length > 0">
        <div class="list">
          <div class="list-item" v-for="item in message_records">
            <div class="text">这是一条后台推送</div>
            <div class="time">2022-01-10 10:00:00</div>
          </div>
        </div>
      </div>
      <div class="nodata flex flex-column flex-x-center flex-y-center">
        <img class="no-data" src="../../static/images/no-data.png" alt="">
        <div class="text">您当前没有消息通知哦～</div>
      </div>
    </div>
  </div>
</template>


<style scoped lang="scss">
.container {
  width: 100%;
  height: 100%;
  background: #fff;

  .content {
    padding: 24rpx;

    .list {
      .list-item {
        background: rgba(0, 0, 0, 0.05);
        padding: 36rpx 24rpx;
        box-sizing: border-box;
        border-radius: 20rpx;
        margin-bottom: 24rpx;
        font-size: 28rpx;

        .text {
          padding-bottom: 36rpx;
          border-bottom: 1px solid rgba(0, 0, 0, 0.05);
          margin-bottom: 18rpx;
        }

        .time {
          color: rgba(0, 0, 0, 0.39);
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
