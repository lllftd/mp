<template>
  <div class="custom-tab-bar">
    <div
      v-for="(tab, index) in tabs"
      :key="index"
      :class="['tab-item', { active: selected === index }]"
      :style="getTabStyle(index)"
      @click="switchTab(index)"
    >
      <image v-if="selected === index" :src="tab.selectedIconPath" class="icon" />
      <image v-else :src="tab.iconPath" class="icon" />
      <div>
        {{ tab.text }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { onShow } from "@dcloudio/uni-app";
import { ref, nextTick, watch } from "vue";
import { redTabBar } from "./tabImg";
// const baseImgUrl = import.meta.env.VITE_BASIC_PREVIEW_URL
// const baseImgUrl = 'http://coolsystem.oss-cn-beijing.aliyuncs.com/'

// 动态设置 tab 的颜色
const getTabStyle = (index) => {
  return {
    color: selected.value === index ? redTabBar.selectedColor : "#979797", // 可以替换为动态的颜色值
  };
};

const selected = ref(0); // 当前选中的 tab 索引
const tabs = [
  { pagePath: "/pages/index/index", text: "推荐" },
  { pagePath: "/pages/community/index", text: "社群" },
  { pagePath: "/pages/activity/index", text: "活动" },
  { pagePath: "/pages/mine/index", text: "我的" },
];

redTabBar.tabBarItems.forEach((item, index) => {
  tabs[index] = {
    ...tabs[index],
    iconPath: item.iconPath, // 新的图标路径
    selectedIconPath: item.selectedIconPath, // 选中状态下的图标路径
  };
});

// 更新选中状态
const updateSelected = () => {
  const pages = getCurrentPages();
  const currentPage = pages[pages.length - 1]; // 获取当前活跃页面
  const currentPath = `/${currentPage.route}`; // 当前页面路径

  // 根据路径匹配设置 selected
  const index = tabs.findIndex((tab) => tab.pagePath === currentPath);
  if (index !== -1) {
    selected.value = index;
  }
};

// 切换 tab
const switchTab = (index) => {
  nextTick(() => {
    selected.value = index;
  });
  uni.switchTab({
    url: tabs[index].pagePath,
  });
};

// 页面加载时初始化选中状态
onShow(() => {
  updateSelected();
});

// 监听页面切换，动态更新选中状态
watch(() => getCurrentPages(), updateSelected);
</script>

<style scoped>
.icon {
  height: 48rpx;
  width: 48rpx;
}

.custom-tab-bar {
  position: fixed;
  z-index: 999;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 156rpx;
  background-color: #fff;
  display: flex;
  justify-content: space-around;
  align-items: center;
  box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.1);
}

.tab-item {
  flex: 1;
  text-align: center;
  color: #666;
  font-family: Yuanti SC;
  font-size: 22rpx;
  font-weight: 400;
  line-height: 16px;
}

.tab-item.active {
  font-weight: bold;
}
</style>
