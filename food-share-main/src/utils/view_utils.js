export const NAV_TARGET = {}

//打开目标页面
export const NAV_TO = (routerName, params = null, events = null) => {
  if (params) {
    var querystring = '?';
    Object.keys(params).forEach(key => {
      querystring = querystring + key + '=' + params[key] + '&';
    });
    uni.navigateTo({
      url: routerName + querystring.slice(0, -1),
      events
    });
  } else {
    uni.navigateTo({
      url: routerName,
      events
    });
  }
};

//打开目标页面，同时关闭当前页
export const NAV_RED = (routerName, params = null) => {
  if (params) {
    var querystring = '?';
    Object.keys(params).forEach(key => {
      querystring = querystring + key + '=' + params[key] + '&';
    });
    uni.redirectTo({
      url: routerName + querystring.slice(0, -1)
    });
  } else {
    uni.redirectTo({
      url: routerName
    });
  }
};

//关闭所有页面，打开到应用内的某个页面。
export const NAV_LAUNCH = (routerName, params = null) => {
  if (params) {
    var querystring = '?';
    Object.keys(params).forEach(key => {
      querystring = querystring + key + '=' + params[key] + '&';
    });
    uni.reLaunch({
      url: routerName + querystring.slice(0, -1)
    });
  } else {
    uni.reLaunch({
      url: routerName
    });
  }
};

//跳转至某个tab页
export const NAV_TAB = routerName => {
  uni.switchTab({
    url: routerName
  });
};

//关闭页面, 参数非必填
//默认关闭一个页面，可通过参数决定关闭多少页面
export const NAV_BACK = num => {
  uni.navigateBack({
    delta: num || 1
  });
};

//执行上一个页面的函数名称
export const NAV_NOTI = (funcName, params) => {
  let pages = getCurrentPages(); //页面栈

  if (pages.length > 1) {
    let beforePage = pages[pages.length - 2];
    beforePage[funcName](params);
  }
};

//展示HUD 加载中... 禁止交互 需与HUD_DISMISS搭配使用
let isLoading = false, isToast = false;
let loadingCount = 0;
let callback = null;
let delayTime = 0;
if (uni.getSystemInfoSync().platform == "android") {
  delayTime = 0;
} else {
  delayTime = 200;
}

export const HUD_SHOW = (title='加载中...') => {
  loadingCount++;
  if (!isLoading) {
    isLoading = true;
    uni.showLoading({
      title,
      mask: true
    });
  }
};
export const HUD_SHOW_UPLOAD = (title='正在上传...') => {
  loadingCount++;
  if (!isLoading) {
    isLoading = true;
    uni.showLoading({
      title,
      mask: true
    });
  }
};

//关闭HUD
export const HUD_DISMISS = () => {
  loadingCount--;
  setTimeout(() => {
    if (loadingCount == 0) {
      isLoading = false;
      uni.hideLoading({
        success: function () {
          callback && callback();
          callback = null;
        }
      });
    }
  }, delayTime);
};

export const TOAST_SHOW_SUCCESS = (str, time = 2000) => {
  if (isLoading) {
    callback = function () {
      uni.showToast({
        icon: 'success',
        title: str || '操作成功',
        duration: time
      });
    };
  } else {
    uni.showToast({
      icon: 'success',
      title: str || '操作成功',
      duration: time
    });
  }
};

export const TOAST_SHOW_INFO = str => {
  callback = function () {
    uni.showToast({
      icon: 'none',
      title: str,
      duration: 2000
    });
  };
  uni.showToast({
    icon: 'none',
    title: str,
    duration: 2000,
    complete: () => {
      callback = null;
    }
  });
};

export const MODAL_SHOW = ({title,content,showCancel=true,cancelText,cancelColor,confirmText,confirmColor,success,fail,complete}) => {
  uni.showModal({
    title: title || "温馨提示",
    content: content || "提示的内容",
    showCancel: showCancel,
    cancelText: cancelText || "取消",
    cancelColor: cancelColor || "#4A4A4A",
    confirmText: confirmText || "确认",
    confirmColor: confirmColor || "#aaa",
    success: success || function(){},
    fail: fail || function(){},
    complete: complete || function(){}
  });
};