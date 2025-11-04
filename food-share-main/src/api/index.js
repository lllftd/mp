import request from "@/utils/request";

// 微信用户登录
export const login = data => {
  return request({
    url: "/client/user/login",
    method: "post",
    data
  })
}

// 微信用户登出
export const logout = data => {
  return request({
    url: "/client/user/logout",
    method: "post",
    data
  })
}

// 获取用户信息
export const get_user_info = ({ id }) => {
  return request({
    url: `/client/user/info/${id}`,
    method: 'get'
  })
}

// 获取兴趣标签字典
export const get_tags = params => {
  return request({
    url: "/client/dict/tag",
    method: "get",
    params
  })
}

// 更改用户信息
export const update_user_info = data => {
  return request({
    url: "/client/user/update",
    method: "post",
    data
  })
}

// 获取推文类型列表
export const get_tweet_types = params => {
  return request({
    url: "/client/tweets/tweetsType",
    method: "get",
    params
  })
}

// 获取推文-通过点赞量或发布时间
export const get_tweets = data => {
  return request({
    url: "/client/tweets/page",
    method: "POST",
    data
  })
}

// 获取详情 
export const get_tweet_detail = ({ id }) => {
  return request({
    url: `/client/tweets/detail/${id}`,
    method: "get"
  })
}

// 推文点赞收藏
export const tweet_like_collect = data => {
  return request({
    url: "/client/tweets/tweetsLikeCollect",
    method: "post",
    data
  })
}

// 推文点赞收藏查询
export const get_tweet_records = params => {
  return request({
    url: "/client/tweets/tweetsRecord",
    method: "get",
    params
  })
}

// 查询当前推文是否点赞收藏
export const get_tweet_is_like_collect = ({ tweetsId }) => {
  return request({
    url: `/client/tweets/tweetsIsLikeCollect/${tweetsId}`,
    method: "get",
  })
}

// 推文浏览
export const tweet_browse = ({ tweetsId }) => {
  return request({
    url: `/client/tweets/tweetsBrowse/${tweetsId}`,
    method: "post"
  })
}

// 获取推文评价列表
export const get_tweet_comments = ({ tweetsId }) => {
  return request({
    url: `/client/tweets/tweetsEvaluateList/${tweetsId}`,
    method: "get"
  })
}

// 发布推文评价
export const publish_tweet_comment = data => {
  return request({
    url: "/client/tweets/tweetsEvaluate",
    method: "post",
    data
  })
}

// 推文点赞收藏浏览查询
export const get_tweet_browse_records = data => {
  return request({
    url: "/client/tweets/tweetsRecord",
    method: "post",
    data
  })
}

// 查询某人的消息记录
export const get_message_records = params => {
  return request({
    url: "/client/activity/getClientMsg",
    method: "get",
    params
  })
}

// 随机获取十条推文
export const get_rand_tweets = data => {
  return request({
    url: "/client/tweets/rand",
    method: "post",
    data
  })
}

// 分页查询活动
export const get_activity_list = data => {
  return request({
    url: "/client/activity/page",
    method: "post",
    data
  })
}

// 查询某用户参与的活动
export const get_user_activity = (params) => {
  return request({
    url: "/client/activity/joinActivity",
    method: "get",
    params
  })
}

// 参与活动
export const join_activity = data => {
  return request({
    url: "/client/activity/join",
    method: "post",
    data
  })
}

// 查询某用户参加的活动id数组
export const get_user_activity_ids = (params) => {
  return request({
    url: "/client/activity/joinActivityIds",
    method: "get",
    params
  })
}

export const imgUpload = src =>
  new Promise((resolve, reject) => {
    const token = uni.getStorageSync("token").value;
    console.log(token);

    uni.getImageInfo({
      src,
      success: function (imgRes) {
        //上传图片
        uni.uploadFile({
          url:
            import.meta.env.VITE_APP_BASE_URL + '/' +
            "client/upload/imgUpload",
          filePath: imgRes.path,
          name: "file",
          header: {
            authentication: token,
          },
          formData: {},
          success: function (res) {
            // console.log(JSON.parse(res.data));
            const responseData = JSON.parse(res.data);
            if (responseData.code === 200) {
              resolve(responseData.data);
            } else {
              reject();
            }

            // setTimeout(() => {
            //   wx.navigateBack({
            //     delta: 0,
            //   });
            // }, 1500);
          },
          error: function (rev) {
            console.log(rev);
            showToastNoIcon("上传失败");
            reject();
          },
        });
      },
      fail: function (srev) {
        console.log(srev);
        showToastNoIcon("图片获取失败");
        reject();
      },
    });
  });