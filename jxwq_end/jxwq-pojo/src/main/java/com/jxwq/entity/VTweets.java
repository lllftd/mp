package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;

/**
 * 推文表
 *
 * @TableName tweets
 */
@EqualsAndHashCode(callSuper = true)
@TableName(value = "v_tweets")
@Data
public class VTweets extends Tweets implements Serializable {
    @TableField(exist = false)
    private static final long serialVersionUID = 1L;

    public VTweets() {
        super();
    }

    /**
     * 推文类型 - 父id
     */
    private String typePidName;
    /**
     * 推文类型 - 子id 可以有多个 逗号隔开
     */
    private String typeCidNames;

}