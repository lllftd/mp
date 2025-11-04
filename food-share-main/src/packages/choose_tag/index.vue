<template>
    <div>
        <div class="container">
            <img class="bg" src="../../static/images/bg2.png" alt="">
            <div class="content flex flex-column flex-y-center">
                <div class="title">请选择您的兴趣标签</div>
                <scroll-view scroll-y="true" style="height: 1200rpx;">
                    <div class="tag-box flex flex-wrap flex-x-center">
                        <div class="tag" :class="{ active: activeIndex.includes(tag) }" v-for="(tag, index) in tags"
                            :key="index" @click="selectTag(tag)">
                            {{ tag }}
                        </div>
                    </div>
                </scroll-view>
                <div class="btn" @click="goIndex">选好了，下一步</div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { get_tags, update_user_info } from "@/api";

const tags = ref([])
const activeIndex = ref([])

const selectTag = (tag) => {
    if (activeIndex.value.includes(tag)) {
        activeIndex.value = activeIndex.value.filter(i => i !== tag)
    } else {
        activeIndex.value.push(tag)
    }
}

const goIndex = () => {
    if (activeIndex.value.length == 0) {
        uni.showToast({
            title: '请选择5个标签',
            icon: 'none'
        })
        return
    }else if (activeIndex.value.length > 5) {
        uni.showToast({
            title: '最多选择5个标签',
            icon: 'none'
        })
        return
    }
    let tagStr = activeIndex.value.join(',')

    update_user_info({
        tags: tagStr
    }).then(res => {
        if(res.code === 200){
            uni.setStorageSync('userInfo', {
                ...uni.getStorageSync('userInfo'),
                tags: tagStr
            })
            uni.showToast({title: '保存成功',icon: 'none'})
            setTimeout(() => {
                uni.switchTab({
                    url: '/pages/index/index'
                })
            }, 1000)
        }
    })

}

const getTags = async () => {
    const res = await get_tags()
    tags.value = res.data.split(',')
}

onMounted(() => {
    const alselectTag = uni.getStorageSync('userInfo').tags?.split(',') || [];
    if (alselectTag.length > 0) {
        activeIndex.value = alselectTag
    }
    getTags()
})
</script>
<style lang="scss">
.container {
    width: 100%;
    height: 100%;
    position: relative;

    .bg {
        position: absolute;
        width: 100%;
        height: 100%;
        z-index: 0;
    }

    .content {
        position: absolute;
        z-index: 10;
        padding: 24rpx;

        .title {
            text-align: center;
            margin-bottom: 24rpx;
        }

        .tag-box {
            height: fit-content;
            margin-bottom: 20rpx;

            .tag {
                font-size: 28rpx;
                padding: 20rpx 35rpx;
                border-radius: 16rpx;
                background: #fff;
                margin: 0 16rpx 42rpx;
            }

            .active {
                color: #fff;
                background: #006241;
            }
        }

        .btn {
            width: 648rpx;
            height: 96rpx;
            background: #006241;
            border-radius: 16rpx;
            text-align: center;
            line-height: 96rpx;
            color: #fff;
        }
    }
}
</style>
