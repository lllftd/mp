package com.jxwq.config;

import com.jxwq.interceptor.JwtTokenAdminInterceptor;
import com.jxwq.interceptor.JwtTokenClientInterceptor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurationSupport;
import springfox.documentation.builders.ApiInfoBuilder;
import springfox.documentation.builders.PathSelectors;
import springfox.documentation.builders.RequestHandlerSelectors;
import springfox.documentation.service.ApiInfo;
import springfox.documentation.spi.DocumentationType;
import springfox.documentation.spring.web.plugins.Docket;

import javax.annotation.Resource;
import java.io.File;

/**
 * 配置类，注册web层相关组件
 */
@Configuration
@Slf4j
public class WebMvcConfiguration extends WebMvcConfigurationSupport {

    /**
     * 资源映射路径 前缀
     */
    @Value("${file.prefix}")
    public String localFilePrefix;

    /**
     * 图片资源映射路径 前缀
     */
    @Value("${file.img-prefix}")
    public String localFilePrefixImg;

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

    @Resource
    private JwtTokenAdminInterceptor jwtTokenAdminInterceptor;

    @Resource
    private JwtTokenClientInterceptor jwtTokenClientInterceptor;

    /**
     * 注册自定义拦截器
     *
     * @param registry 拦截器注册器
     */
    protected void addInterceptors(InterceptorRegistry registry) {
        log.info("开始注册自定义拦截器...");
        // 注册管理端拦截器
        registry.addInterceptor(jwtTokenAdminInterceptor)
                .addPathPatterns("/admin/**") // 拦截所有以/admin开头的请求
                // .addPathPatterns("/**") // 拦截所有请求
                .addPathPatterns("/system/**") // 拦截所有以/system开头的请求
                .excludePathPatterns("/admin/user/login"); // 排除登录接口

        // 注册客户端拦截器
        registry.addInterceptor(jwtTokenClientInterceptor)
                .addPathPatterns("/client/**")
                // .excludePathPatterns() // 追加排除的
                .excludePathPatterns("/client/user/login")
                .excludePathPatterns("/client/tweets/rand");
    }

    /**
     * 通过knife4j生成接口文档
     *
     * @return 接口文档
     */
    @Bean
    public Docket docket() {
        ApiInfo apiInfo = new ApiInfoBuilder()
                .title("接口文档")
                .version("1.0")
                .description("项目接口文档")
                .build();
        return new Docket(DocumentationType.SWAGGER_2)
                .apiInfo(apiInfo)
                .select()
                .apis(RequestHandlerSelectors.basePackage("com.jxwq.controller"))
                .paths(PathSelectors.any())
                .build();
    }

    /**
     * 设置静态资源映射
     *
     * @param registry 资源映射注册器
     */
    protected void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/doc.html").addResourceLocations("classpath:/META-INF/resources/");
        registry.addResourceHandler("/webjars/**").addResourceLocations("classpath:/META-INF/resources/webjars/");
        // 本地文件上传路径
        registry.addResourceHandler(localFilePrefix + "/**")
                .addResourceLocations("file:" + localFilePath + File.separator);
        // 本地图片上传路径
        registry.addResourceHandler(localFilePrefixImg + "/**")
                .addResourceLocations("file:" + localFilePath + "\\images" + File.separator);
    }

}
