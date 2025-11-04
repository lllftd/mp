package com.jxwq.dto;

import lombok.Data;

import java.io.Serializable;

@Data
public class EndUserDetailDto implements Serializable {

    // id
    private Integer id;

    // 用户名
    private String userName;

    // 用户昵称
    private String nickName;

    // 头像
    private String avatar;

    // 手机号
    private String phone;

    // 性别
    private String sex;

}
