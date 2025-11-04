package com.jxwq.dto;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import org.hibernate.validator.constraints.Length;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.Pattern;
import java.io.Serializable;


@Data
@ApiModel(description = "后台用户登录时传递的数据模型")
public class EndUserLoginDto implements Serializable {

    // https://blog.csdn.net/qq_38974638/article/details/115396937 校验
    @NotEmpty(message = "账号不能为空")
    @Length(min = 4, max = 16, message = "账号长度为 3-16 位")
    @Pattern(regexp = "^[A-Za-z0-9]+$", message = "账号格式为数字以及字母")
    @ApiModelProperty("账号")
    private String username;

    @NotEmpty(message = "密码不能为空")
    // @Pattern(regexp = "^[A-Za-z0-9_.]+$", message = "密码只能包含数字、字母、下划线和点")
    @Pattern(regexp = "^[A-Za-z0-9_.-@]+$", message = "密码格式有误")
    @Length(min = 5, max = 16, message = "密码长度为 5-16 位")
    @ApiModelProperty("密码")
    private String password;

}
