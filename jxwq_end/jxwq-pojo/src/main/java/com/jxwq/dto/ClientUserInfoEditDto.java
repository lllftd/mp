package com.jxwq.dto;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import java.io.Serializable;

@Data
public class ClientUserInfoEditDto implements Serializable {

    private static final long serialVersionUID = 1L;

    private Integer id; // 主键
    /**
     * 用户昵称
     */
    @NotEmpty(message = "用户昵称不能为空")
    @ApiModelProperty("用户昵称")
    private String nickName;
    /**
     * 用户头像
     */
    @NotEmpty(message = "用户头像不能为空")
    @ApiModelProperty("用户头像")
    private String avatar;

}