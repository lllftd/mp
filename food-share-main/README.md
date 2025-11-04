# 目录结构
|-- order_client_2.0_uni
    |-- .env
    |-- .gitignore
    |-- .prettierrc.js
    |-- auto-imports.d.ts    自动导入配置 自动生成不用管
    |-- components.d.ts      自动导入配置 自动生成不用管
    |-- favicon.ico
    |-- index.html
    |-- package.json
    |-- README.md
    |-- shims-uni.d.ts
    |-- vite.config.js       vite配置文件
    |-- .vscode
    |   |-- extensions.json  推荐使用的工作区插件
    |-- public
    |-- src
        |-- App.vue
        |-- main.js
        |-- manifest.json
        |-- pages.json
        |-- shime-uni.d.ts
        |-- uni.scss
        |-- api
        |   |-- index.js
        |-- assets
        |-- components       组件目录
        |-- constant         常量目录
        |   |-- index.js
        |-- packages         分包
        |-- pages            主包
        |-- static           静态资源目录
        |-- store            状态管理
        |   |-- system.js
        |   |-- user.js
        |-- styles
        |   |-- main.scss    全局样式
        |-- utils            工具类

# pages.json 和 manifest.json 写了注释 编辑器会爆红，但不影响使用 
临时解决爆红方法 语言设置为jsonc

# 自动导入函数
配置了函数自动导入插件 常用的函数可以不用导入使用 如:
uniapp的 onLaunch, onShow, onHide ...
vue的 onMounted, onUnmounted , ref, reactive, computed, watch ...

# 自动导入组件
配置了组件自动导入插件 在src/components目录下的组件可自动导入 

# 获取系统导航栏宽高
```javascript
    import { useSystemStore } from "@/store/system";
    const systemStore = useSystemStore();
    console.log(systemStore.statusBarHeight); //状态栏的高度，单位px
    console.log(systemStore.navigationTop); // 导航栏顶部高度
    console.log(systemStore.navigationHei); // 导航栏高度，默认值为 20
    console.log(systemStore.paddingLeft); // 导航栏左侧内边距，默认值为 0
```

# 安装依赖
yarn

# 启动项目 微信小程序
npm run dev:mp-weixin

# 打包项目 微信小程序
npm run build:mp-weixin

# 切换小程序id 在src/manifest.json 两个位置以及 utils/appId里面切换 切换图标样式在tabImg里

# 切换使用的首页，个人中心等页面的切换在utils/pageChonfig.js里

# 小程序开发部署流程

    1、增加开发者与体验者账号

    2、配置主营类目

    3、配置appId 以及存储小程序密钥
    
    4、配置商户支付相关id和密钥，RSAkey值等（后台管理处）

    5、配置好服务器域名，包括后台域名以及上传文件域名，获取图片cdn的域名

    6、点餐堂食桌码部分需要开启扫描二维码打开小程序，规则为
         {domain}/table/{商户id}/shop?tableid=%shopid=
        将校验文件存储在v2的商户id文件夹下
    
    7、进行一轮测试，使得支付，扫码，等功能没有问题

    8、指导商家使用后台增加菜品、商品等功能，进行发版
