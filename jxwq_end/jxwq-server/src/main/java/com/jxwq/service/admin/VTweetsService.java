package com.jxwq.service.admin;

import com.baomidou.mybatisplus.extension.service.IService;
import com.jxwq.entity.VTweets;

import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【tweets(推文表)】的数据库操作Service
 * @createDate 2024-08-31 01:32:10
 */
public interface VTweetsService extends IService<VTweets> {

    // 随机获取10条推文
    List<Map<String, Object>> randomTweets();

}
