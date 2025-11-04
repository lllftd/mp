package com.jxwq.mapper;


import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.jxwq.entity.VTweets;

import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【tweets(推文表)】的数据库操作Mapper
 * @createDate 2024-08-31 01:32:10
 * @Entity generator.domain.Tweets
 */
public interface VTweetsMapper extends BaseMapper<VTweets> {

    // 随机获取10条推文
    List<Map<String, Object>> randomTweets();

}




