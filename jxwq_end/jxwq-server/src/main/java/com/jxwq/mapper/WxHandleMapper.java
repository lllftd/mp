package com.jxwq.mapper;

import org.apache.ibatis.annotations.Mapper;

import java.util.Map;

/**
 * @author: jxwq
 * @date: 2024/12/18 上午 12:15
 * @description:
 */
@Mapper
public interface WxHandleMapper {

    Map<String, Object> getAccessToken();

    void setAccessToken(String accessToken, long expireTimestamp);
}
