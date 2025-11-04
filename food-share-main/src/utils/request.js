import axios from "axios";
import mpAdapter from "axios-miniprogram-adapter";
import { getCache } from "@/utils/token";
import { login } from "@/api";

axios.defaults.adapter = mpAdapter;

const instance = axios.create({
    /* baseURL小程序用vite代理不行 只能靠这里 */
    // baseURL: import.meta.env.VITE_APP_BASE_URL + import.meta.env.VITE_APP_BASE_API, timeout: 1000 * 7, //超时时间
    baseURL: import.meta.env.VITE_APP_BASE_URL, timeout: 1000 * 7, //超时时间
    headers: {
        // "Content-type": "application/json;charset=utf-8",
        // "Access-Control-Allow-Credentials": true,
        // "Access-Control-Allow-Origin": "*",
        // "Access-Control-Allow-Headers": "application/json",
        "accept": "*/*", "content-type": "application/json",
    },
});

//请求拦截 携带token
instance.interceptors.request.use((config) => {
    if (config.url !== '/client/tweets/tweetsLikeCollect'
        && config.url !== '/client/tweets/tweetsLikeCancel'
        && config.url !== '/client/tweets/rand'
        && !config.url.includes('/client/user/info')
        && !config.url.includes('/client/user/info')
        && !config.url.includes('/client/tweets/tweetsBrowse')
    ) {

        uni.showLoading({
            title: '加载中', mask: true
        })
    }
    config.headers = config.headers || {};
    const token = getCache("token");
    // if(!token) {
    //     uni.login({
    //         success({ code }) {
    //           login({ js_code: code }).then((response) => {
    //             uni.showToast({ title: "登录成功", icon: "none" });
    //             uni.setStorageSync("token", response.info.token);
    //             // setTimeout(() => {
    //             //   uni.reLaunch({
    //             //     url: '/pages/index/index'
    //             //   })
    //             // }, 1500)

    //           })
    //         },
    //         fail(err) {
    //           console.log(err);
    //         }
    //       });
    // }
    if (token) {
        config.headers['authentication'] = `${token}`;  // 使用Bearer方式传递token
    }
    // if (token && config.data) {
    //     config.data["token"] = token;
    // }
    // if (token && config.params) {
    //     config.params = { ...config.params, token };
    // }
    return config;
}, (error) => Promise.reject(error),);
let isShowingAuthModal = false;
//响应拦截 拿到结果 响应成功或者失败
instance.interceptors.response.use((response) => {
    let code = response?.data?.code;
    uni.hideLoading()
    if (code === 200) {
        return Promise.resolve(response.data); //等于200 将成功信息返回出去
    } else if (code === 401) {
        // 关闭当前页面，跳转到登录页面 清除pinia ?
        setTimeout(() => {
            uni.navigateTo({ url: "/pages/login/index" });
        }, 1500);
        // if (!isShowingAuthModal) { // 🔐 只允许执行一次
        //     isShowingAuthModal = true;

        //     const pages = getCurrentPages();
        //     const currentPage = pages[pages.length - 1];
        //     const currentPageUrl = `/${currentPage.route}`;

        //     // 只有不是登录页或个人中心时才提示
        //     if (currentPageUrl !== "/pages/login/index" && currentPageUrl !== "/pages/mine/index") {
        //         uni.showModal({
        //             title: '提示',
        //             content: '登录已过期，请重新登录',
        //             showCancel: false,
        //             success: (res) => {
        //                 uni.removeStorageSync('token');
        //                 uni.navigateTo({ url: "/pages/login/index" });
        //                 isShowingAuthModal = false; // ✅ 弹窗关闭后释放锁（可选）
        //             },
        //             fail: () => {
        //                 isShowingAuthModal = false; // 防止异常时锁死
        //             }
        //         });
        //     } else {
        //         isShowingAuthModal = false; // 如果是登录页，直接释放
        //     }
        // }
        return Promise.reject(response.data);
    } else {

        uni.showToast({ title: response.data.msg, icon: "none", duration: 2000 });
        return Promise.reject(response.data.msg); //reject表示失败，给他信息返回出去
    }

}, (error) => {
    //断网处理或者请求超时
    uni.hideLoading()
    let code = error?.response?.status || error?.response?.data.code;
    if (code === 401) {
        setTimeout(() => {
            uni.navigateTo({ url: "/pages/login/index" });
        }, 1500);
        // if (!isShowingAuthModal) {
        //     isShowingAuthModal = true;

        //     const pages = getCurrentPages();
        //     const currentPage = pages[pages.length - 1];
        //     const currentPageUrl = `/${currentPage.route}`;

        //     if (currentPageUrl !== "/pages/login/index" && currentPageUrl !== "/pages/mine/index") {
        //         uni.showModal({
        //             title: '提示',
        //             content: '登录已过期，请重新登录',
        //             showCancel: false,
        //             success: (res) => {
        //                 uni.removeStorageSync('token');
        //                 uni.navigateTo({ url: "/pages/login/index" });
        //                 isShowingAuthModal = false;
        //             },
        //             fail: () => {
        //                 isShowingAuthModal = false;
        //             }
        //         });
        //     } else {
        //         isShowingAuthModal = false;
        //     }
        // }
        return Promise.reject("登录已过期");
    } else if (code === 403) {
        uni.showToast({ title: error.response.data.msg, icon: "none", duration: 2000 });
    }
    let statusCode = [404, 405, 500];
    if (statusCode.includes(code)) uni.showToast({ title: "接口异常，请联系管理员！", icon: "none", duration: 2000 });
    return Promise.reject("接口异常，请联系管理员！");
},);

export default instance;
