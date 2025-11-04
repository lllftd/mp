package com.jxwq.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.Date;

/**
 * 活动表
 *
 * @TableName activity
 */
@TableName(value = "activity")
@Data
public class Activity implements Serializable {
    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
    /**
     * 主键
     */
    @TableId(type = IdType.AUTO)
    private Integer id;
    /**
     * 活动标题/名称
     */
    private String actTitle;
    /**
     * 活动类型 1商家 2同城
     */
    private String actType;
    /**
     * 活动地区
     */
    private String actLocation;
    /**
     * 活动地区编码
     */
    private String actLocationCode;
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
    private Date actStartDate;
    /**
     * 活动结束时间
     */
    @JsonFormat(pattern = "yyyy-MM-dd", timezone = "GMT+8")
    private Date actEndDate;
    /**
     * 参与条件
     */
    private String joinCondition;
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
     * 修改人
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private String updateUser;
}