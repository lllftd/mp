package com.jxwq.service.admin.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.Tweets;
import com.jxwq.mapper.TweetsMapper;
import com.jxwq.service.admin.TweetsService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * @author jxwq
 * @description 针对表【tweets(推文表)】的数据库操作Service实现
 * @createDate 2024-08-31 01:32:10
 */
@Service
@Transactional(rollbackFor = Exception.class)
public class TweetsServiceImpl extends ServiceImpl<TweetsMapper, Tweets>
        implements TweetsService {

    @Resource
    TweetsMapper tweetsMapper;

    // 查询个人的点赞、收藏、浏览记录总数用来分页
    @Override
    public Integer countTweetsRecords(String type, Integer clientUserId) {
        return tweetsMapper.countTweetsRecords(type, clientUserId);
    }

    @Override
    public Long typeUseCountInTweets(int id) {
        QueryWrapper<Tweets> queryWrapper = new QueryWrapper<>();

        // 一级类目
        if (Objects.nonNull(id)) {
            queryWrapper.eq("tweets_type_pid", id);
        }

        // 二级类目
        if (Objects.nonNull(id)) {
            queryWrapper.or(orWrapper -> orWrapper
                    // .in("tweets_type_cid", id) // tweets_type_cid IN () 查出来的不是正确的
                    .apply("FIND_IN_SET({0}, tweets_type_cid)", id));
        }

        // SELECT COUNT( * ) AS total FROM tweets WHERE (tweets_type_pid = 20 OR (tweets_type_cid IN (20) AND FIND_IN_SET(20, tweets_type_cid)))
        // 改进版 👇
        // SELECT COUNT( * ) AS total FROM tweets WHERE (tweets_type_pid = 17 OR (FIND_IN_SET(17, tweets_type_cid)))

        return tweetsMapper.selectCount(queryWrapper);
    }

    // 查询当前推文是否被点赞、收藏 - 根据推文id和用户id
    @Override
    public List<Map<String, Object>> getIsLikeCollect(Integer clientUserId, Integer tweetsId) {
        return tweetsMapper.getIsLikeCollect(clientUserId, tweetsId);
    }

    // 查询用户点赞收藏浏览
    @Override
    public List<Map<String, Object>> getRecordListByTypeAndUserId(Integer userId, String type, Integer pageSize, Integer offset) {
        return tweetsMapper.getRecordListByTypeAndUserId(userId, type, pageSize, offset);
    }

    @Override
    public void insertTweetsRecord(Integer clientUserId, Integer tweetsId, String type) {
        tweetsMapper.insertTweetsRecord(clientUserId, tweetsId, type);
    }

    @Override
    public void deleteTweetsRecord(Integer tweetsRecordId) {
        tweetsMapper.deleteTweetsRecord(tweetsRecordId);
    }

    @Override
    public List<Map<String, Object>> getBrowseRecord(Integer clientUserId, Integer tweetsId) {
        return tweetsMapper.getBrowseRecord(clientUserId, tweetsId);
    }

    @Override
    public List<Map<String, Object>> getLikeRecord(Integer clientUserId, Integer tweetsId) {
        return tweetsMapper.getLikeRecord(clientUserId, tweetsId);
    }

    @Override
    public void updateTweetsRecordCreateTime(Integer clientUserId, Integer id) {
        tweetsMapper.updateTweetsRecordCreateTime(clientUserId, id);
    }

    @Override
    public void updateTweetsCount(Map<String, Object> map) {
        tweetsMapper.updateTweetsCount(map);
    }

    @Override
    public List<Map<String, Object>> getTweetsEvaluate(Integer tweetsId) {
        return tweetsMapper.getTweetsEvaluate(tweetsId);
    }

    @Override
    public void insertTweetsEvaluate(Map<String, Object> map) {
        tweetsMapper.insertTweetsEvaluate(map);
    }
}




