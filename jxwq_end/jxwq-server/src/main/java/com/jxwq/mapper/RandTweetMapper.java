package com.jxwq.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * @author: jxwq
 * @date: 2024/10/24 下午 09:39
 * @description: 处理随机推荐推文的Mapper
 */
@Mapper
public interface RandTweetMapper {

    /**
     * 根据用户ID获取喜欢的推文子类
     *
     * @param userId 用户ID
     * @return 喜欢的推文ID列表
     */
    List<Map<String, Object>> getLikedTweetIdsByUserId(@Param("userId") Integer userId);

    /**
     * 根据关键词获取推文类型的ID
     *
     * @param keyword 搜索关键词
     * @return 推文类型ID列表
     */
    List<Integer> getTypeIdsByKeyword(@Param("keyword") String keyword);

    /**
     * 根据推文类型ID获取推文
     *
     * @param typeIds 推文类型ID列表
     * @return 推文列表
     */
    List<Map<String, Object>> getTweetsByTypeIds(@Param("list") List<Integer> typeIds);

    /**
     * 根据已喜欢的推文ID推荐相似的推文
     *
     * @param likedTweetIds 已喜欢的推文ID列表
     * @return 相似的推文列表
     */
    List<Map<String, Object>> getSimilarTweets(@Param("list") List<String> likedTweetIds);

    /**
     * 随机获取推文
     *
     * @param count 需要获取的推文数量
     * @return 随机推文列表
     */
    List<Map<String, Object>> getRandomTweets(@Param("count") int count);

}
