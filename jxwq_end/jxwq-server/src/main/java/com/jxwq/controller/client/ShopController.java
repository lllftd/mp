package com.jxwq.controller.client;

import com.jxwq.result.Result;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;

@RestController("userShopController")
@RequestMapping("/user/shop")
public class ShopController {

    private static final String KEY = "SHOP_STATUS";

    @Resource
    private RedisTemplate redisTemplate;

    // 查询店铺状态
    @GetMapping("/status")
    public Result getStatus() {
        Integer status = (Integer) redisTemplate.opsForValue().get(KEY);

        return Result.success(status);
    }
}