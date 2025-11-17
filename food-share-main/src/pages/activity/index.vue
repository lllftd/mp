<script setup>
import CusTabBar from "@/components/CusTabBar";
import { ref, onMounted } from "vue";
import { get_activity_list } from "@/api";

const activityList = ref([]);

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

const fetchActivityList = async () => {
    const res = await get_activity_list({
        page: page.value,
        pageSize: pageSize.value,
    });
    if (res.code === 200) {
        activityList.value = [...activityList.value, ...res.data.rows];
        total.value = res.data.total;
        pages.value = res.data.totalPage;
    }
}

const goDetail = (item) => {
    uni.navigateTo({
        url: `/packages/activity_detail/index?item=${JSON.stringify(item)}`
    });
}

onMounted(() => {
    fetchActivityList();
});


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
            <div v-if="activityList.length > 0" class="content">
                <div class="list">
                    <div @click="goDetail(item)" class="list-item flex" v-for="item in activityList">
                        <img class="cover" :src="item.actImg" alt="">
                        <div class="box flex flex-column">
                            <div>
                                <div class="title">{{ item.actTitle }}</div>
                                <div class="desc">{{ item.actDescribe }}</div>
                            </div>
                            <div class="meta-info">
                                <div class="location flex flex-y-center" v-if="item.actLocation">
                                    <img class="location-icon" src="../../static/images/svgIcon/ip.svg" alt="">
                                    {{ formatLocation(item.actLocation) }}
                                </div>
                                <div class="time flex flex-y-center">
                                    <img class="time-icon" src="../../static/images/svgIcon/time.svg" alt="">
                                    {{ item.actStartDate }} - {{ item.actEndDate }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div v-else class="nodata flex flex-column flex-x-center flex-y-center">
                <img class="no-data" src="../../static/images/no-data.png" alt="">
                <div class="text">当前没有任何活动哦～</div>
            </div>
        </div>
        <CusTabBar />
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

                .meta-info {
                    display: flex;
                    flex-direction: column;
                    gap: 8rpx;
                    margin-top: 12rpx;
                }

                .location {
                    .location-icon {
                        width: 28rpx;
                        height: 28rpx;
                        margin-right: 10rpx;
                    }

                    font-size: 24rpx;
                    color: #6F6F6F;
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
        }
    }
}
</style>
