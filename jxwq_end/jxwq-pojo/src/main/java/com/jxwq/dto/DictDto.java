package com.jxwq.dto;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.validation.constraints.NotEmpty;
import java.io.Serializable;

/**
 * @author: jxwq
 * @date: 2024/08/25
 * @description:
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@ApiModel(description = "接收前端字典的增删改")
public class DictDto implements Serializable {

    private static final long serialVersionUID = 1L;

    // 字典id
    @ApiModelProperty(value = "字典id")
    private Integer id;

    // 字典名称
    @NotEmpty(message = "字典名称不能为空")
    @ApiModelProperty(value = "字典名称")
    private String dictName;

    // 字典值
    @NotEmpty(message = "字典值不能为空")
    @ApiModelProperty(value = "字典值")
    private String dictValue;

}