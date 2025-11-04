package com.jxwq.service.admin;

import com.baomidou.mybatisplus.extension.service.IService;
import com.jxwq.entity.Tweets;

import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【tweets(推文表)】的数据库操作Service
 * @createDate 2024-08-31 01:32:10
 */

public interface TweetsService extends IService<Tweets> {

    // 查询个人的点赞、收藏、浏览记录总数用来分页
    Integer countTweetsRecords(String type, Integer clientUserId);

    // 查询一二级类目是否被使用
    Long typeUseCountInTweets(int id);

    // 查询当前推文是否被点赞、收藏 - 根据推文id和用户id
    List<Map<String, Object>> getIsLikeCollect(Integer clientUserId, Integer tweetsId);

    // 查询用户点赞收藏浏览
    List<Map<String, Object>> getRecordListByTypeAndUserId(Integer userId, String type, Integer pageSize, Integer offset);

    // 增加一条记录
    void insertTweetsRecord(Integer clientUserId, Integer tweetsId, String type);

    // 删除一条记录
    void deleteTweetsRecord(Integer tweetsRecordId);

    // 获取浏览记录
    List<Map<String, Object>> getBrowseRecord(Integer clientUserId, Integer tweetsId);

    // 获取点赞记录
    List<Map<String, Object>> getLikeRecord(Integer clientUserId, Integer tweetsId);

    // 更新推文记录表时间
    void updateTweetsRecordCreateTime(Integer clientUserId, Integer id);

    // 推文表 点赞/收藏/浏览数量加减
    void updateTweetsCount(Map<String, Object> map);

    // 获取推文评论内容
    List<Map<String, Object>> getTweetsEvaluate(Integer tweetsId);

    // 发布评论
    void insertTweetsEvaluate(Map<String, Object> map);

}
