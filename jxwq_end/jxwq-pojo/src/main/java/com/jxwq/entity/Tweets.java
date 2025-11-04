package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 推文表
 *
 * @TableName tweets
 */
@TableName(value = "tweets")
@Data
public class Tweets implements Serializable {
    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
    /**
     * 主键
     */
    @TableId(type = IdType.AUTO)
    private Integer id;
    /**
     * 推文类型 - 父id
     */
    private Integer tweetsTypePid;
    /**
     * 推文类型 - 子id 可以有多个 逗号隔开
     */
    private String tweetsTypeCid;
    /**
     * 推文标题
     */
    private String tweetsTitle;
    /**
     * 推文作者
     */
    private String tweetsUser;
    /**
     * 推文简介
     */
    private String tweetsDescribe;
    /**
     * 推文图片
     */
    private String tweetsImg;
    /**
     * 推文内容
     */
    private String tweetsContent;
    /**
     * 点赞数
     */
    private Integer likeNum;
    /**
     * 收藏数
     */
    private Integer collectNum;
    /**
     * 浏览数
     */
    private Integer browseNum;
    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private LocalDateTime createTime;
    /**
     * 更新时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private LocalDateTime updateTime;
    /**
     * 创建人
     */
    @TableField(fill = FieldFill.INSERT)
    private String createUser;
    /**
     * 小程序创建人
     */
    private String clientCreateUser;
    /**
     * 修改人
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private String updateUser;
}