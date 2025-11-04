package com.jxwq.service.client.impl;

import com.jxwq.mapper.RandTweetMapper;
import com.jxwq.service.client.RandTweetService;
import com.jxwq.utils.CommonUtils;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.*;

/**
 * @author: jxwq
 * @date: 2024/10/24 下午 09:51
 * @description:
 */
@Service
public class RandTweetServiceImpl implements RandTweetService {

    @Resource
    RandTweetMapper randTweetMapper;

    /**
     * 随机获取元素从list中
     *
     * @param list  列表
     * @param count 获取的数量
     * @return 随机获取的元素
     */
    public static List<String> getRandomElements(List<String> list, int count) {
        if (list == null || list.isEmpty() || count <= 0) {
            return Collections.emptyList();
        }

        List<String> tempList = new ArrayList<>(list);
        Collections.shuffle(tempList);

        int endIndex = Math.min(count, tempList.size());
        return tempList.subList(0, endIndex);
    }

    @Override
    public List<Map<String, Object>> recommendTweets(Integer clientUserId, String searchTypeKeyword) {
        // 根据用户ID获取喜欢的推文ID列表
        List<String> likedTweetIds = null;
        if (clientUserId != null) {
            Set<String> likedTweetIdsByUserIdSet = new HashSet<>();
            List<Map<String, Object>> likedTweetIdsByUserId = randTweetMapper.getLikedTweetIdsByUserId(clientUserId);
            for (Map<String, Object> map : likedTweetIdsByUserId) {
                String tweets_type_cid = CommonUtils.stringValue(map.get("tweets_type_cid"));
                if (!tweets_type_cid.contains(",")) {
                    // 没有逗号说明是单个类型
                    likedTweetIdsByUserIdSet.add(tweets_type_cid);
                } else {
                    // 逗号分隔多个类型 并重
                    String[] ids = tweets_type_cid.split(",");
                    likedTweetIdsByUserIdSet.addAll(Arrays.asList(ids));
                }
            }

            likedTweetIds = new ArrayList<>(likedTweetIdsByUserIdSet);
        }

        // 计算推荐推文
        List<Map<String, Object>> recommendedTweets = calculateRecommendedTweets(likedTweetIds, searchTypeKeyword);

        // 如果推荐的推文数量不足10条，则随机补充
        while (recommendedTweets.size() < 10) {
            List<Map<String, Object>> randomTweets = randTweetMapper.getRandomTweets(10 - recommendedTweets.size());
            for (Map<String, Object> map : randomTweets) {
                if (!recommendedTweets.contains(map)) {
                    recommendedTweets.add(map);
                }
            }
        }

        return recommendedTweets.subList(0, 10); // 返回前10条推文
    }

    public List<Map<String, Object>> calculateRecommendedTweets(List<String> likedTweetIds, String searchTypeKeyword) {
        // 如果有搜索关键词，优先根据关键词查找推文类型
        if (searchTypeKeyword != null && !searchTypeKeyword.trim().isEmpty()) {
            List<Integer> typeIds = randTweetMapper.getTypeIdsByKeyword(searchTypeKeyword);
            // 根据关键词搜索到的类型id是空的话，则返回空列表
            if (typeIds.isEmpty()) {
                return new ArrayList<>();
            }

            // 不是空的话根据类型id推荐对应的推文
            List<Map<String, Object>> list = randTweetMapper.getTweetsByTypeIds(typeIds);
            // 打乱列表顺序
            Collections.shuffle(list);
            return list;
        } else if (likedTweetIds != null && !likedTweetIds.isEmpty()) {
            // 如果有喜欢的推文ID，根据这些ID推荐相似的推文
            // 随机取5个id，然后根据这些id推荐相似的推文
            List<String> randomIds = getRandomElements(likedTweetIds, 5);
            return randTweetMapper.getSimilarTweets(randomIds);
        } else {
            // 如果没有特定条件，随机推荐10条 适用于没有登录的用户并且没有输入搜索关键词 或者是新用户,没有喜欢的推文
            return randTweetMapper.getRandomTweets(10);
        }
    }

}



