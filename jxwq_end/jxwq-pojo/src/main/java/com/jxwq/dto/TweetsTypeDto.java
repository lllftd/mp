package com.jxwq.dto;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotEmpty;
import java.io.Serializable;

/**
 * @author: jxwq
 * @date: 2024/9/14
 * @description:
 */
@Data
public class TweetsTypeDto implements Serializable {
    private static final long serialVersionUID = 1L;

    private Integer id; // 主键

    @ApiModelProperty("类目名称")
    @NotBlank(message = "类目名称不能为空")
    private String name;

    @ApiModelProperty("父类型id")
    private Integer parentId;

}
