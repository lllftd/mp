package com.jxwq.mapper;


import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.jxwq.entity.Tweets;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【tweets(推文表)】的数据库操作Mapper
 * @createDate 2024-08-31 01:32:10
 * @Entity generator.domain.Tweets
 */
public interface TweetsMapper extends BaseMapper<Tweets> {

    // 查询个人推文记录总数
    Integer countTweetsRecords(@Param("type") String type, @Param("clientUserId") Integer clientUserId);

    // 查询当前推文是否被点赞、收藏 - 根据推文id和用户id
    List<Map<String, Object>> getIsLikeCollect(@Param("clientUserId") Integer clientUserId, @Param("tweetsId") Integer tweetsId);

    // 查询用户点赞收藏浏览
    List<Map<String, Object>> getRecordListByTypeAndUserId(@Param("clientUserId") Integer userId, @Param("type") String type,
                                                           @Param("pageSize") Integer pageSize, @Param("offset") Integer offset);

    // 增加一条记录
    void insertTweetsRecord(@Param("clientUserId") Integer clientUserId,
                            @Param("tweetsId") Integer tweetsId,
                            @Param("type") String type);

    // 删除一条记录
    void deleteTweetsRecord(@Param("id") Integer tweetsRecordId);

    // 获取浏览记录
    List<Map<String, Object>> getBrowseRecord(@Param("clientUserId") Integer clientUserId, @Param("tweetsId") Integer tweetsId);

    // 获取点赞记录
    List<Map<String, Object>> getLikeRecord(@Param("clientUserId") Integer clientUserId, @Param("tweetsId") Integer tweetsId);

    // 更新推文记录表时间
    void updateTweetsRecordCreateTime(@Param("clientUserId") Integer clientUserId, @Param("id") Integer id);

    // 推文表 点赞/收藏/浏览数量加减
    void updateTweetsCount(Map<String, Object> map);

    // 获取推文评论内容
    List<Map<String, Object>> getTweetsEvaluate(@Param("tweetsId") Integer tweetsId);

    // 发布评论
    void insertTweetsEvaluate(Map<String, Object> map);

}




