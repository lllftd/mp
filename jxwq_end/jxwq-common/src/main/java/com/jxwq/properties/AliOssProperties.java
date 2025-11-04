package com.jxwq.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "jxwq.alioss")
@Data
public class AliOssProperties {

    private String endpoint; // 访问域名 例如 oss-cn-beijing.aliyuncs.com
    private String replacePrefix; // 替换前缀 自定义域名
    private String accessKeyId; // 密钥ID
    private String accessKeySecret; // 密钥
    private String bucketName; // 存储桶名
    private String dir; // 上传目录

}
