package com.jxwq.dto;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import org.hibernate.validator.constraints.Length;

import javax.validation.constraints.NotEmpty;
import java.io.Serializable;

@Data
public class CrowdDto implements Serializable {

    private static final long serialVersionUID = 1L;

    private Integer id; // 主键

    @NotEmpty(message = "社群标题不能为空")
    @Length(min = 3, max = 16, message = "社群标题长度为 3-12 位")
    @ApiModelProperty("社群标题")
    private String crowdTitle; // 社群标题/名称

    @ApiModelProperty("社群类型")
    private String crowdType; // 社群类型

    @NotEmpty(message = "社群头像不能为空")
    @ApiModelProperty("社群头像")
    private String crowdImg; // 社群头像

    @NotEmpty(message = "社群描述不能为空")
    @ApiModelProperty("社群描述")
    private String crowdDescribe; // 社群描述

    // 如果有其他需要在DTO中传递的字段，可以在这里继续添加
    // 例如：private String someOtherField;

}