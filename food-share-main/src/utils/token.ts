/**
 * 设置token到本地存储
 * @param token
 */
export const setToken = (token: string) => {
  try {
    uni.setStorageSync('token', token)
  } catch (e) {
    console.error('set token error', e)
  }
}

/**
 * 从本地获取token
 * @returns token
 */
export const getLocalToken = () => {
  try {
    return uni.getStorageSync('token')
  } catch (e) {
    console.error('get token error', e)
  }
  return ''
}

/**
 * 设置缓存
 * @param key 缓存key
 * @param value 缓存数据
 * @param expireSeconds 缓存过期时间，秒
 */
function setCache (key: any, value: any, expireSeconds: any) {
  console.log(key, value, expireSeconds);
  
  uni.setStorage({
    key: key,
    data: {
      value: value,
      expireTime: expireSeconds
    },
    success: function() {
      console.log('缓存设置成功');
    }
  });
}

/**
 * 获取缓存
 * @param key
 */
function getCache (key: any) {
  const res = uni.getStorageSync(key);
  if (res && res.expireTime > Date.now()) {
    return res.value;
  } else {
    uni.removeStorage({
      key: key,
      success: function() {
        console.log('缓存已过期，已移除');
      }
    });
    return null; // 缓存过期，返回null
  }
}

export {
  setCache,
  getCache
}

