package com.jxwq.service.client;

public interface RecommendationFeedbackService {

    /**
     * 保存用户对推荐的反馈
     *
     * @param userId 用户ID
     * @param tweetsId 推文ID
     * @param feedback like / dislike
     */
    void saveFeedback(Integer userId, Integer tweetsId, String feedback);
}

