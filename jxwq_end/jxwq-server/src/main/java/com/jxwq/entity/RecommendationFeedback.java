package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 用户推荐反馈表
 */
@Data
@TableName("recommendation_feedback")
public class RecommendationFeedback implements Serializable {

    @TableId
    private Long id;

    private Integer clientUserId;

    private Integer tweetsId;

    /**
     * 反馈类型：like / dislike
     */
    private String feedback;

    /**
     * 奖励值：喜欢为1，不喜欢为-1
     */
    private Integer reward;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}

