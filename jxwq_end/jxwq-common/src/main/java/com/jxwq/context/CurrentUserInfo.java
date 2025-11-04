package com.jxwq.context;

import lombok.Data;

@Data
public class CurrentUserInfo {

    // 用户类型 "end" 后台 "client" 客户端
    public String userType;

    // 用户名
    public String name;

    // 用户id
    public Integer id;

}
