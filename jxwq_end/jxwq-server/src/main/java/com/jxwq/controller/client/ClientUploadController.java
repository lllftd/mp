package com.jxwq.controller.client;


import com.jxwq.constant.MessageConstant;
import com.jxwq.context.BaseContext;
import com.jxwq.result.AjaxResult;
import com.jxwq.utils.file.AliOssUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import javax.annotation.Resource;
import java.io.File;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;


@RestController
@RequestMapping("/client/upload")
@Slf4j
public class ClientUploadController {

    @Resource
    private AliOssUtil aliOssUtil;

    /**
     * 上传文件存储在本地的根路径
     */
    @Value("${file.path}")
    private String localFilePath;

    /**
     * 注入操作系统属性
     */
    @Value("#{systemProperties['os.name']}")
    private String systemPropertiesName;

    // springboot 上传图片并回显 https://blog.csdn.net/THcoding_Cat/article/details/92004141

    /**
     * 图片上传
     *
     * @param file 图片文件
     * @return 图片名称
     */
    @PostMapping("/imgUpload")
    public AjaxResult upload(@RequestParam("file") MultipartFile file) {

        if (file.isEmpty()) {
            return AjaxResult.error(MessageConstant.UPLOAD_EMPTY);
        }

        String originalFilename = file.getOriginalFilename(); // 原来的图片名

        String suffix = null; // 后缀名 为空过不来后端 前端做了校验
        if (originalFilename != null) {
            suffix = "." + originalFilename.split("\\.")[originalFilename.split("\\.").length - 1]; // 获取截取的后缀名(最后一个.)
        }

        String uuid = UUID.randomUUID().toString().replace("-", ""); // 随机生成uuid
        List<String> imgParams = getImgUploadPath(uuid, suffix);
        String newFileName = imgParams.get(0); // 新的图片名
        String uploadPath = imgParams.get(1); // 上传后的路径

        try {
            // 上传到本地
            // file.transferTo(new File(uploadPath));
            // 上传到阿里云oss
            String filePath = aliOssUtil.upload(file.getBytes(), newFileName);
            log.info("小程序图片上传成功：链接- {}, 上传用户为{}", filePath, BaseContext.getCurrentUserInfo());
            return AjaxResult.success(MessageConstant.UPLOAD_SUCCESS, filePath);
        } catch (Exception e) {
            log.error("小程序图片上传失败,上传用户为{}", BaseContext.getCurrentUserInfo());
            return AjaxResult.error(MessageConstant.UPLOAD_FAILED);
        }
    }

    /**
     * 获取处理后的图片名称和上传路径
     *
     * @param uuid   图片的uuid
     * @param suffix 图片的后缀名
     * @return 图片名称和上传路径
     */
    private List<String> getImgUploadPath(String uuid, String suffix) {
        String fileName = uuid + suffix; // 新的图片名 uuid.后缀名

        // 上传图片
        // ApplicationHome applicationHome = new ApplicationHome(this.getClass());
        // String pre = applicationHome
        //         .getDir()
        //         .getParentFile().getParentFile().getParentFile()
        //         .getAbsolutePath() // 获取绝对路径
        //         + "\\uploadFiles\\images\\";
        String pre = localFilePath + "images\\"; // 读取配置文件中的路径
        if (!new File(pre).exists()) {
            // 文件夹不存在则创建
            Boolean dirMakeFlag = new File(pre).mkdirs();
        }

        return Arrays.asList(fileName, pre + fileName); // 图片名称 和 上传后的路径
    }
}
