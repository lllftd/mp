package com.jxwq.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "jxwq.jwt")
@Data
public class JwtProperties {

    /**
     * 后台管理用户生成jwt令牌相关配置
     */
    private String adminSecretKey;
    private long adminTtl;
    private String adminTokenName;

    /**
     * 用户端微信用户生成jwt令牌相关配置
     */
    private String clientSecretKey;
    private long clientTtl;
    private String clientTokenName;

}
