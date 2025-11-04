package com.jxwq.service.admin;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.jxwq.mapper.WxHandleMapper;
import com.jxwq.properties.WeChatProperties;
import com.jxwq.utils.CommonUtils;
import com.jxwq.utils.HttpClientUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.Map;

/**
 * @author: jxwq
 * @date: 2024/12/18 上午 12:11
 * @description:
 */

@Slf4j
@Service
public class WxHandleService {

    private static final String GET_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token";

    @Resource
    private WeChatProperties weChatProperties; // 微信配置

    @Resource
    private WxHandleMapper wxHandleMapper;

    // 获取access_token
    public String getAccessToken() {

        Map<String, Object> AccessTokenMap = wxHandleMapper.getAccessToken();
        // expire_timestamp = 0 代表初始值 需要获取access_token，然后设置过期时间并返回
        if (CommonUtils.object2Int(AccessTokenMap.get("expire_timestamp")) == 0) {
            return getAccessTokenWithWx();
        }

        // 判断当前时间是否大于过期时间戳，如果是 则需要重新获取access_token
        long expireTimestamp = CommonUtils.object2Long(AccessTokenMap.get("expire_timestamp"));
        if (System.currentTimeMillis() / 1000 > expireTimestamp) {
            return getAccessTokenWithWx();
        }

        // 否则，直接返回access_token
        return AccessTokenMap.get("value").toString();

    }

    // 设置access_token
    public void setAccessToken(String accessToken, long expireTimestamp) {
        wxHandleMapper.setAccessToken(accessToken, expireTimestamp);
    }

    /**
     * 调用微信接口服务，获取access_token
     *
     * @return openid
     */
    private String getAccessTokenWithWx() {
        // 调用微信接口服务
        Map<String, String> map = new HashMap<>();
        map.put("appid", weChatProperties.getAppid());
        map.put("secret", weChatProperties.getSecret());
        map.put("grant_type", "client_credential");
        String json = HttpClientUtil.doGet(GET_ACCESS_TOKEN_URL, map);

        JSONObject jsonObject = JSON.parseObject(json);
        if (jsonObject.containsKey("errcode")) {
            log.error("获取access_token失败，错误码：{}，错误信息：{}", jsonObject.getString("errcode"), jsonObject.getString("errmsg"));
            throw new RuntimeException("获取access_token失败，请联系管理员");
        }

        log.info("获取access_token成功");

        // 返回expires_in 是7200 表示2小时过期，这里设置1个半小时过期 5400
        setAccessToken(jsonObject.getString("access_token"), (System.currentTimeMillis() / 1000) + 5400);

        return jsonObject.getString("access_token");
    }
}
