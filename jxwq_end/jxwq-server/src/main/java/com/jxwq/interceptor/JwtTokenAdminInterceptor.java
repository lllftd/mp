package com.jxwq.interceptor;

import com.jxwq.constant.HttpStatus;
import com.jxwq.constant.JwtClaimsConstant;
import com.jxwq.constant.SystemConstant;
import com.jxwq.context.BaseContext;
import com.jxwq.context.CurrentUserInfo;
import com.jxwq.properties.JwtProperties;
import com.jxwq.utils.CommonUtils;
import com.jxwq.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.annotation.Resource;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * 后台管理系统jwt令牌校验的拦截器
 */
@Component
@Slf4j
public class JwtTokenAdminInterceptor implements HandlerInterceptor {

    @Resource
    private JwtProperties jwtProperties;

    /**
     * 校验jwt
     *
     * @param request  表示当前的 HTTP 请求，你可以从中获取请求信息，如请求头、参数等
     * @param response 表示当前的 HTTP 响应，你可以设置响应头、状态码等。
     * @param handler  表示当前请求将要调用的处理器方法。通过这个对象，你可以获取到处理器的方法、返回类型等信息。
     * @return true 表示继续执行后续的拦截器和处理器；false 表示中断请求，直接返回响应。
     * @throws Exception 异常信息
     */
    @Override
    public boolean preHandle(@Nullable HttpServletRequest request, @Nullable HttpServletResponse response, @Nullable Object handler) throws Exception {
        // 判断当前拦截到的是Controller的方法还是其他资源
        if (!(handler instanceof HandlerMethod)) {
            // 当前拦截到的不是动态方法，直接放行
            return true;
        }

        if (request == null || response == null) {
            throw new IllegalArgumentException("Request or Response is null");
        }

        // 从请求头中获取令牌
        String token = request.getHeader(jwtProperties.getAdminTokenName());

        if (token == null || token.isEmpty()) {
            // 如果token无效，返回错误信息并阻止请求继续处理
            response.setStatus(HttpStatus.UNAUTHORIZED); // 401
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":401,\"msg\":\"请先登录\"} ");
            return false;
        }

        // 校验令牌
        try {
            // log.info("后台jwt校验:{}", token);
            Claims claims = JwtUtil.parseJWT(jwtProperties.getAdminSecretKey(), token);
            // log.info("后台jwt校验成功，解析出来的用户信息 - " + claims);
            CurrentUserInfo currentUserInfo = new CurrentUserInfo();
            Integer endUserId = CommonUtils.string2Int(CommonUtils.stringValue(claims.get(JwtClaimsConstant.END_USER_ID)));
            currentUserInfo.setUserType(SystemConstant.END_USER_TYPE); // 后台端用户类型
            currentUserInfo.setId(endUserId);
            currentUserInfo.setName(claims.get(JwtClaimsConstant.END_USER_NAME).toString());

            // 将 jwt 中解析出来的用户信息添加到 ThreadLocal 中
            BaseContext.setCurrentUserInfo(currentUserInfo);
            // 通过，放行
            return true;
        } catch (Exception ex) {
            log.error("JWT验证失败", ex);
            // 不通过，响应 403 状态码
            response.setStatus(HttpStatus.FORBIDDEN); // 403
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":403,\"msg\":\"验证无效或过期，请重新登录\"} ");
            return false;
        }
    }
}
