<template>
    <div>
        <div class="container" v-if="!loading">
            <div class="user-info flex flex-y-center">
                <img class="avatar" :src="tweetDetail.avatar" alt="">
                <div class="r-box">
                    <div class="name">{{ tweetDetail.tweetsUser }}</div>
                    <div class="time">{{ tweetDetail.createTime }}</div>
                </div>
            </div>
            <swiper class="swiper" circular @change="changeSwiper" style="height: 850rpx;">
                <swiper-item class="slide-item" v-for="(item, index) in JSON.parse(tweetDetail.tweetsImg)" :key="index">
                    <img class="cover-img" :src="item" alt="">
                </swiper-item>
            </swiper>
            <!-- 自定义指示点 -->
            <div class="custom-indicator">
                <div v-for="(item, index) in JSON.parse(tweetDetail.tweetsImg)" :key="index" class="indicator-dot"
                    :class="{ active: currentIndex === index }"></div>
            </div>
            <div class="bot-wrap">
                <div class="info">
                    <div class="title">{{ tweetDetail.tweetsTitle }}</div>
                    <div class="desc">{{ tweetDetail.tweetsContent }}</div>
                    <div class="tags flex flex-y-center">
                        <div class="tag" v-for="(item, index) in tweetDetail.typeCidNames.split(',')" :key="index">{{
                            item }}</div>
                    </div>
                    <div class="ip flex flex-y-center">
                        <img class="ip-icon" src="../../static/images/svgIcon/ip.svg" alt="">
                        {{ tweetDetail.tweetsDescribe }}
                    </div>
                </div>
                <div class="evalute">
                    <div class="title">全部评价</div>
                    <div class="evalute-list" v-if="tweetDetail.comment_list.length">
                        <div class="evalute-item flex" v-for="eva in tweetDetail.comment_list">
                            <img class="user-avatar" :src="eva.avatar" alt="">
                            <div class="r-box">
                                <div class="name">{{ eva.nikeName }}</div>
                                <div class="content">{{ eva.evaluateContent }}</div>
                                <div class="time">{{ eva.createTime.split(' ')[0] }}</div>
                            </div>
                        </div>
                    </div>
                    <div v-else class="no-data"
                        style="text-align: center;margin: 40rpx auto;font-size: 28rpx; color: #A3A3A3;">- 暂无评价 -</div>
                </div>
            </div>
            <div class="bot-input flex flex-y-center">
                <input @confirm="publishComment" class="input" v-model="commentContent" type="text"
                    placeholder="聪明的我有话想说~" placeholder-class="my-placeholder">
                <div class="actions flex flex-y-center">
                    <img @click="tweetActions(tweetDetail.id, 'like', tweetDetail.is_like)" class="icon2"
                        :src="tweetDetail.is_like ? '../../static/images/svgIcon/like-a.svg' : '../../static/images/svgIcon/like2.svg'"
                        alt="">
                    <img @click="tweetActions(tweetDetail.id, 'collect', tweetDetail.is_collect)" class="icon3"
                        :src="tweetDetail.is_collect ? '../../static/images/svgIcon/collect-a.svg' : '../../static/images/svgIcon/collect2.svg'"
                        alt="">
                    <img class="icon" src="../../static/images/svgIcon/evalute.svg" alt="">
                    <img class="icon" src="../../static/images/svgIcon/share.svg" alt="">
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { get_tweet_detail, get_user_info, tweet_like_collect, tweet_browse, get_tweet_comments, get_tweet_is_like_collect, publish_tweet_comment } from "@/api";
const currentIndex = ref(0);
const changeSwiper = (event) => {
    const detail = event.detail || {};
    currentIndex.value = detail.current;
}

const tweetId = ref(null);
const loading = ref(true);
const tweetDetail = ref(null);
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
// 获取推文的详情
const getTweetDetail = async () => {
    loading.value = true;
    try {
        const res = await get_tweet_detail({ id: tweetId.value });
        if (res.code !== 200) return;

        const tweet = res.data;

        // 1. 获取用户信息（发帖人）
        // const userRes = await get_user_info({ id: tweet.createUser }).catch(() => ({}));

        // 2. 获取评论列表
        const commentRes = await get_tweet_comments({ tweetsId: tweet.id }).catch(() => ({}));
        const comments = commentRes.code === 200 ? commentRes.data : [];

        // 3. 批量获取评论用户的头像和昵称（去重）
        const userIds = [...new Set(comments.map(c => c.clientUserId))];
        const userAvatarMap = {};

        await Promise.all(
            userIds.map(async (userId) => {
                try {
                    const res = await get_user_info({ id: userId });
                    if (res.code === 200) {
                        userAvatarMap[userId] = res.data.avatar || 'https://cdn.dxgr.org.cn/175705528917713061_avatar_1757055294.png';
                    } else {
                        userAvatarMap[userId] = 'https://cdn.dxgr.org.cn/175705528917713061_avatar_1757055294.png';
                    }
                } catch (err) {
                    userAvatarMap[userId] = 'https://cdn.dxgr.org.cn/175705528917713061_avatar_1757055294.png';
                }
            })
        );

        // 4. 给评论加上头像和昵称
        const comment_list = comments.map(c => ({
            ...c,
            avatar: userAvatarMap[c.clientUserId],
            // 如果后端没返回昵称，也可以在这里补
        }));

        // 5. 整合数据
        tweetDetail.value = {
            ...tweet,
            // user_info: userRes.data || null,
            comment_list,
            is_like: false,
            is_collect: false,
            avatar: avatars[hashString(tweet.tweetsUser) % avatars.length],
        };

        // 单独请求点赞收藏状态（可放最后）
        try {
            console.log(tweet.id);

            const isLikeCollectRes = await get_tweet_is_like_collect({ tweetsId: tweet.id });
            tweetDetail.value.is_like = isLikeCollectRes.data?.like || false;
            tweetDetail.value.is_collect = isLikeCollectRes.data?.collect || false;
            tweetDetail.value.likeRecordId = isLikeCollectRes.data?.likeRecordId || "";
            tweetDetail.value.collectRecordId = isLikeCollectRes.data?.tweetsRecordId || "";
        } catch (e) { }
        tweet_browse({ tweetsId: tweet.id });

        console.log("获取推文详情成功", tweetDetail.value);

    } catch (error) {
        console.error("获取推文详情失败", error);
    } finally {
        loading.value = false;
    }
};

// 点赞收藏操作
const tweetActions = async (id, type, isflag) => {
    if (type == 'like') {
        tweetDetail.value.is_like = !tweetDetail.value.is_like;
        const tweetsRecordId = tweetDetail.value.likeRecordId;
        tweet_like_collect({
            tweetsId: id,
            type,
            tweetsRecordId,
            flag: !isflag ? 'add' : ''
        }).then(() => {
            uni.showToast({
                title: !isflag ? '点赞成功' : '取消点赞',
                icon: 'none',
                duration: 1000
            });
        });;
    } else {
        tweetDetail.value.is_collect = !tweetDetail.value.is_collect;
        const tweetsRecordId = tweetDetail.value.collectRecordId;
        tweet_like_collect({
            tweetsId: id,
            type,
            tweetsRecordId,
            flag: !isflag ? 'add' : ''
        }).then(() => {
            uni.showToast({
                title: !isflag ? '收藏成功' : '取消收藏',
                icon: 'none',
                duration: 1000
            });
        });
    }
}

// 发表评价
const commentContent = ref('');
const commentImg = ref('');
const publishComment = async () => {
    if (!commentContent.value) return;
    const res = await publish_tweet_comment({
        tweetsId: tweetId.value,
        openId: uni.getStorageSync("userInfo")?.openId || "",
        evaluateContent: commentContent.value,
        evaluateImg: commentImg.value || ""
    });
    if (res.code === 200) {
        commentContent.value = '';
        getTweetDetail();
    }
}
onLoad((options) => {
    tweetId.value = Number(options.id);
    getTweetDetail()
});
</script>
<style lang="scss">
:deep(.my-placeholder) {
    font-size: 28rpx;
    color: #A3A3A3;
}

.container {
    width: 100%;
    height: 100%;
    background: #fff;

    .user-info {
        padding: 18rpx 24rpx;
        font-size: 24rpx;

        .avatar {
            width: 64rpx;
            height: 64rpx;
            border-radius: 50%;
            margin-right: 20rpx;
        }

        .time {
            color: #999999;
        }
    }

    .slide-item {
        .cover-img {
            width: 100%;
            height: 830rpx;
        }
    }

    .custom-indicator {
        display: flex;
        justify-content: center;
        align-items: center;

        .indicator-dot {
            width: 30rpx;
            height: 8rpx;
            background-color: rgba(186, 186, 186, 0.29);
            margin: 0 4rpx;
            transition: all 0.3s ease;
            border-radius: 16rpx;

            &.active {
                background-color: #8FD427;
                width: 34rpx;
            }
        }
    }

    .bot-wrap {
        padding: 24rpx 24rpx 180rpx;

        .info {
            .title {
                font-size: 32rpx;
                font-weight: 600;
                letter-spacing: 2%;
                margin-bottom: 18rpx;
            }

            .desc {
                font-size: 28rpx;
                color: #5C4C4C;
                line-height: 48rpx;
            }

            .tags {
                margin: 8px 8rpx 18rpx 0;

                .tag {
                    color: #fff;
                    background: #000;
                    font-size: 20rpx;
                    padding: 4rpx 10rpx;
                    border-radius: 8rpx;
                    margin-right: 8rpx;
                }
            }

            .ip {
                border: 1px solid rgba(255, 243, 240, 1);
                background: #FFF9F7;
                font-size: 28rpx;
                border-radius: 16rpx;
                padding: 18rpx 24rpx;
                box-sizing: border-box;
                color: #474747;
                margin-bottom: 38rpx;
                .ip-icon {
                    width: 24rpx;
                    height: 32rpx;
                    margin-right: 18rpx;
                }
            }
        }

        .evalute {
            .evalute-item {
                margin-bottom: 28rpx;
            }

            .title {
                font-weight: 500;
                margin-bottom: 24rpx;
            }

            .user-avatar {
                width: 80rpx;
                height: 80rpx;
                border-radius: 50%;
                margin-right: 16rpx;
            }

            .r-box {
                .name {
                    font-size: 28rpx;
                    margin-bottom: 12rpx;
                }

                .content {
                    color: #86919A;
                    margin-bottom: 12rpx;
                    font-size: 28rpx;
                }

                .time {
                    font-size: 24rpx;
                    color: rgba(134, 145, 154, 0.52);
                }
            }
        }
    }

    .bot-input {
        background: #fff;
        height: 180rpx;
        padding: 0 24rpx;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 99;

        .input {
            width: 380rpx;
            height: 80rpx;
            border-radius: 16rpx;
            background: #F4F7F9;
            padding-left: 20rpx;
        }

        .actions {
            .icon2 {
                width: 58rpx;
                height: 58rpx;
                margin-left: 28rpx;
            }

            .icon3 {
                width: 40rpx;
                height: 40rpx;
                margin-left: 28rpx;
            }

            .icon {
                width: 48rpx;
                height: 48rpx;
                margin-left: 28rpx;
            }

        }
    }
}
</style>
