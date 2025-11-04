package com.jxwq.dto;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import org.hibernate.validator.constraints.Length;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.io.Serializable;
import java.util.Date;

@Data
public class ActivityDto implements Serializable {

    private static final long serialVersionUID = 1L;

    private Integer id; // 主键

    @NotEmpty(message = "活动标题不能为空")
    @Length(min = 3, max = 16, message = "活动标题长度为 3-12 位")
    @ApiModelProperty("活动标题")
    private String actTitle; // 活动标题/名称

    @NotEmpty(message = "活动类型不能为空")
    @ApiModelProperty("活动类型")
    private String actType; // 活动类型

    @NotEmpty(message = "活动地区不能为空")
    @ApiModelProperty("活动地区")
    private String actLocation; // 活动地区

    @NotEmpty(message = "活动地区编码不能为空")
    @ApiModelProperty("活动地区编码")
    private String actLocationCode; // 活动地区编码

    @NotEmpty(message = "活动图片不能为空")
    @ApiModelProperty("活动图片")
    private String actImg; // 活动图片

    @NotEmpty(message = "活动描述不能为空")
    @ApiModelProperty("活动描述")
    private String actDescribe; // 活动描述

    @NotNull(message = "活动开始时间不能为空")
    @ApiModelProperty("活动开始时间")
    private Date actStartDate; // 活动开始时间

    @NotNull(message = "活动结束时间不能为空")
    @ApiModelProperty("活动结束时间")
    private Date actEndDate; // 活动结束时间

    @NotEmpty(message = "参与条件不能为空")
    @ApiModelProperty("参与条件")
    private String joinCondition; // 参与条件

}