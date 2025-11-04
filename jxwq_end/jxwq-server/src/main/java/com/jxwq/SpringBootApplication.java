package com.jxwq;

import lombok.extern.slf4j.Slf4j;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.transaction.annotation.EnableTransactionManagement;

@org.springframework.boot.autoconfigure.SpringBootApplication
@EnableTransactionManagement // 开启注解方式的事务管理
@Slf4j
@MapperScan("com.jxwq.mapper")
public class SpringBootApplication {
    public static void main(String[] args) {
        SpringApplication.run(SpringBootApplication.class, args);
        log.info("\n" +
                "  |\\    \\ \\ \\ \\ \\ \\ \\      __           ___\n" +
                "  |  \\    \\ \\ \\ \\ \\ \\ \\   | O~-_    _-~~   ~~-_\n" +
                "  |   >----|-|-|-|-|-|-|--|  __/   /  BELIEVE  )\n" +
                "  |  /    / / / / / / /   |__\\   <              )\n" +
                "  |/     / / / / / / /             \\_   ME !  _)\n" +
                "                                     ~--___--~     \n" +
                "  程序启动成功，请访问 http://localhost:8080/doc.html 访问接口文档"
        );
    }
}
