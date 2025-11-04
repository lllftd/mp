package com.jxwq.vo;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@ApiModel(description = "后台用户登录成功返回的数据格式")
public class EndUserLoginVo implements Serializable {

    @ApiModelProperty("主键值")
    private Integer id;

    @ApiModelProperty("用户名")
    private String userName;

    @ApiModelProperty("姓名")
    private String nickName;

    @ApiModelProperty("头像")
    private String avatar;

    @ApiModelProperty("jwt令牌")
    private String token;

    @ApiModelProperty("过期时间")
    private Long expiresIn;

}
