package com.jxwq.service.client.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.jxwq.entity.RecommendationFeedback;
import com.jxwq.mapper.RecommendationFeedbackMapper;
import com.jxwq.service.client.RecommendationFeedbackService;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import javax.annotation.Resource;

@Service
public class RecommendationFeedbackServiceImpl implements RecommendationFeedbackService {

    @Resource
    private RecommendationFeedbackMapper recommendationFeedbackMapper;

    @Override
    public void saveFeedback(Integer userId, Integer tweetsId, String feedback) {
        if (userId == null || tweetsId == null || !StringUtils.hasText(feedback)) {
            return;
        }

        String normalized = feedback.toLowerCase();
        if (!"like".equals(normalized) && !"dislike".equals(normalized)) {
            return;
        }

        // 可选：同一用户对同一推文的最新反馈覆盖旧反馈
        LambdaQueryWrapper<RecommendationFeedback> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(RecommendationFeedback::getClientUserId, userId)
                .eq(RecommendationFeedback::getTweetsId, tweetsId);
        recommendationFeedbackMapper.delete(wrapper);

        RecommendationFeedback feedbackEntity = new RecommendationFeedback();
        feedbackEntity.setClientUserId(userId);
        feedbackEntity.setTweetsId(tweetsId);
        feedbackEntity.setFeedback(normalized);
        feedbackEntity.setReward("like".equals(normalized) ? 1 : -1);

        recommendationFeedbackMapper.insert(feedbackEntity);
    }
}

