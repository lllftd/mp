package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 
 * @TableName v_activity_join
 */
@TableName(value ="v_activity_join")
@Data
public class VActivityJoin implements Serializable {
    /**
     * 主键
     */
    private Integer id;

    /**
     * 活动id
     */
    private Integer actId;

    /**
     * 小程序用户id
     */
    private Integer clientUserId;

    /**
     * 创建时间/参与时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")
    private LocalDateTime updateTime;

    /**
     * 创建人
     */
    private String createUser;

    /**
     * 修改人
     */
    private String updateUser;

    /**
     * 活动标题/名称
     */
    private String actTitle;

    /**
     * 活动类型 - 1商家、2同城
     */
    private String actType;

    /**
     * 活动图片
     */
    private String actImg;

    /**
     * 活动描述
     */
    private String actDescribe;

    /**
     * 活动开始时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd", timezone = "GMT+8")
    private LocalDate actStartDate;

    /**
     * 活动结束时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd", timezone = "GMT+8")
    private LocalDate actEndDate;

    /**
     * 参与条件
     */
    private String joinCondition;

    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
}