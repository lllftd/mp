<template>
    <div>
        <div class="container">
            <img class="cover-img" :mode="'widthFix'" :src="activityDetail.actImg" alt="">
            <div class="bot-wrap">
                <div class="info">
                    <div class="title">{{ activityDetail.actTitle }}</div>
                    <div class="item local" v-if="activityDetail.actLocation">
                        <span class="key">活动地区：</span>{{ formatLocation(activityDetail.actLocation) }}
                    </div>
                    <div class="item time"><span class="key">参与时间：</span>{{ activityDetail.actStartDate }} - {{
                        activityDetail.actEndDate }}</div>
                    <div class="item desc"><span class="key">活动描述：</span>{{ activityDetail.actDescribe }}</div>
                </div>
            </div>
            <div v-if="!isJoin" @click="joinActivity" class="btn">参与活动</div>
            <div v-else class="btn is-join">已经参与</div>
        </div>
    </div>
</template>

<script setup>
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { join_activity, get_user_activity_ids } from "@/api"

const activityDetail = ref({});
const isJoin = ref(false)

// 格式化地理位置显示
const formatLocation = (location) => {
    if (!location) return '';
    // 将"天津市/市辖区/河东区"格式化为"天津·河东区"
    const parts = location.split('/').filter(part => part && part !== '市辖区');
    if (parts.length > 0) {
        // 移除"市"、"区"、"县"等后缀，只保留主要部分
        const city = parts[0].replace('市', '');
        const district = parts.length > 1 ? parts[parts.length - 1] : '';
        return district ? `${city}·${district}` : city;
    }
    return location.replace(/\//g, '·');
}

const joinActivity = () => {
    join_activity({
        actId: activityDetail.value.id,
        actTitle: activityDetail.value.actTitle,
        getMsg: uni.getStorageSync("userInfo")?.getMsg === "1",
    }).then(res => {
        uni.showToast({
            title: '参与成功',
            icon: 'none'
        })
    })
}

const getjoinId = () => {
    get_user_activity_ids().then(res => {
        console.log(res.data);
        isJoin.value = res.data.filter(item => item.actId === activityDetail.value.id)
    })
}

onLoad((options) => {
    activityDetail.value = JSON.parse(options.item);
    getjoinId()

});
</script>
<style lang="scss">
:deep(.my-placeholder) {
    font-size: 28rpx;
    color: #A3A3A3;
}

.container {
    position: relative;
    width: 100%;
    height: 100%;
    background: #fff;

    .cover-img {
        width: 100%;
    }

    .bot-wrap {
        padding: 24rpx 24rpx 180rpx;

        .info {
            .title {
                font-size: 32rpx;
                font-weight: 600;
                letter-spacing: 2%;
                margin-bottom: 28rpx;
            }

            .item {
                font-size: 28rpx;
                margin-bottom: 20rpx;
                color: #000;

                .key {
                    color: rgba(0, 0, 0, 0.67)
                }
            }
        }

    }

    .btn {
        position: absolute;
        bottom: 120rpx;
        left: 50%;
        transform: translateX(-50%);
        width: 94%;
        height: 96rpx;
        line-height: 96rpx;
        text-align: center;
        background: #000;
        color: #fff;
        font-size: 32rpx;
        border-radius: 18rpx;
    }
    .is-join {
        background: #A3A3A3 !important;
        color: #fff !important;
    }
}
</style>
