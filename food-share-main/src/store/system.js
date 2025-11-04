import { defineStore } from "pinia";

export const useSystemStore = defineStore("system", {
  state: () => ({
    statusBarHeight: uni.getSystemInfoSync().statusBarHeight, //状态栏的高度，单位px
    navigationTop: 0, // 导航栏顶部高度
    navigationHei: 20, // 导航栏高度，默认值为 20
    paddingLeft: 0, // 导航栏左侧内边距，默认值为 0
  }),
  getters: {
    currTapHeight: () => useSystemStore().navigationTop + useSystemStore().navigationHei + "px", //导航栏顶部+导航栏+px
  },
  actions: {
    getNavInfo() {
      /* 
        https://developers.weixin.qq.com/community/develop/article/doc/0000ecde0e49a85a314c9d44d51013
        使用wx.getSystemInfoSync()获取设备基础信息，
        使用wx.getMenuButtonBoundingClientRect()获取右上角胶囊的信息
        导航栏高度公式：导航栏高度 = 状态栏到胶囊的间距（胶囊距上边界距离-状态栏高度） * 2 + 胶囊高度。
        注：状态栏到胶囊的间距 = 胶囊到下边界距离。所以这里需要*2 
        */
      // 获取系统信息
      const { screenWidth, statusBarHeight } = uni.getSystemInfoSync();
      // 获取胶囊按钮信息
      const { height, top, right } = uni.getMenuButtonBoundingClientRect();
      // 计算左侧内边距
      const paddingLeft = screenWidth - right;
      // 计算导航栏高度
      const navigationHei = (top - statusBarHeight) * 2 + height;

      this.navigationTop = statusBarHeight;
      this.navigationHei = navigationHei;
      this.paddingLeft = paddingLeft;
    },
  },
});
