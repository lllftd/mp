package com.jxwq.dto.pageQuery;

import lombok.Data;

import javax.validation.constraints.NotNull;
import java.io.Serializable;

/**
 * @author: jxwq
 * @date: 2024/8/30
 * @description:
 */
@Data
public class CrowdPageQueryDTO implements Serializable {

    // @NotEmpty 用在集合类上面
    // @NotBlank 用在String上面
    // @NotNull    用在基本类型上

    @NotNull(message = "页码不能为空") // int类型默认值就为0了 校验空会算通过的
    private Integer page; // 页码

    @NotNull(message = "每页条数不能为空")
    private Integer pageSize; // 每页条数

    private String crowdTitle; // 标题

    private String crowdDescribe; // 描述

}
