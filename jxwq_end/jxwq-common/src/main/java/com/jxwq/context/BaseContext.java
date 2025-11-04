package com.jxwq.context;

/**
 * 全局上下文 线程变量
 */
public class BaseContext {

    public static ThreadLocal<CurrentUserInfo> threadLocal = new ThreadLocal<>();

    /**
     * 获取后台用户信息
     *
     * @return 后台用户信息
     */
    public static CurrentUserInfo getCurrentUserInfo() {
        return threadLocal.get();
    }

    /**
     * 设置后台用户信息
     *
     * @param currentUserInfo 后台用户信息
     */
    public static void setCurrentUserInfo(CurrentUserInfo currentUserInfo) {
        threadLocal.set(currentUserInfo);
    }

    /**
     * 移除后台用户信息
     */
    public static void removeCurrentUserInfo() {
        threadLocal.remove();
    }
}
