package com.jxwq.utils.file;

import com.aliyun.oss.ClientException;
import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.OSSException;
import com.aliyun.oss.model.GeneratePresignedUrlRequest;
import com.jxwq.constant.MessageConstant;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;

import java.io.ByteArrayInputStream;
import java.net.URL;
import java.util.Date;

/**
 * aliyun oss工具类
 */
@Data
@AllArgsConstructor
@Slf4j
public class AliOssUtil {

    private String endpoint;
    private String replacePrefix;
    private String accessKeyId;
    private String accessKeySecret;
    private String bucketName;
    private String dir;

    /**
     * 获取设置了过期时间的url
     *
     * @param ossClient      阿里云实例
     * @param bucketName     bucket名称
     * @param fullObjectName 文件名称
     * @param dayNum         过期天数
     * @return 签名后的url
     */
    public static URL getExpiredUrl(OSS ossClient, String bucketName, String fullObjectName, Integer dayNum) {
        // log.info("getExpiredUrl - ossClient,  bucketName,  fullObjectName,  dayNum: {} {} {} {}", ossClient, bucketName, fullObjectName, dayNum);

        long OneDay = 3600L * 1000 * 24; // 一天的毫秒数
        // 生成预签名 URL
        Date expiration = new Date(System.currentTimeMillis() + OneDay * dayNum);
        GeneratePresignedUrlRequest request = new GeneratePresignedUrlRequest(bucketName, fullObjectName);
        request.setExpiration(expiration);
        return ossClient.generatePresignedUrl(request);
    }

    /**
     * 文件上传
     *
     * @param bytes      文件字节数组
     * @param objectName 文件名
     * @return 文件访问路径
     */
    public String upload(byte[] bytes, String objectName) {

        // 创建OSSClient实例。
        OSS ossClient = new OSSClientBuilder().build(endpoint, accessKeyId, accessKeySecret);
        String finallyUrl = null; // 最终处理好并签名的URL

        try {
            // 创建PutObject请求。
            String fullObjectName = dir.isEmpty() ? objectName : dir + objectName;
            ossClient.putObject(bucketName, fullObjectName, new ByteArrayInputStream(bytes));

            // cdn加速
            finallyUrl = "https://" + replacePrefix + "/" + fullObjectName;

            // log.info("文件上传到:{}", finallyUrl);
        } catch (OSSException oe) {
            throw new RuntimeException(MessageConstant.UPLOAD_FAILED);
        } catch (ClientException ce) {
            System.out.println("Caught an ClientException, which means the client encountered " + "a serious internal problem while trying to communicate with OSS, " + "such as not being able to access the network.");
            System.out.println("Error Message:" + ce.getMessage());
        } finally {
            if (ossClient != null) {
                ossClient.shutdown();
            }
        }

        return finallyUrl;
    }

}
