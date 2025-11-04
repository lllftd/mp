<script setup>
// import { onLaunch, onShow, onHide } from "@dcloudio/uni-app"; //配置了自动导入插件 不需要手动导入
import { useSystemStore } from "@/store/system";

// #ifndef H5
useSystemStore().getNavInfo(); //获取导航栏信息 H5环境不获取
// #endif
onShow(() => { });
onHide(() => { });

</script>

<style lang="scss">
/* 注意要写在第一行，同时给style标签加入lang="scss"属性 */
@import "uview-plus/index.scss";
/*每个页面公共css */
@import "./styles/main.scss";
@import "./styles/color.scss";
</style>
