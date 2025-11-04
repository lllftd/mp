package com.jxwq.dto;

import lombok.Data;

import java.io.Serializable;

@Data
public class EmployeePageQueryDto implements Serializable {

    // 后台用户姓名
    private String nickName;

    // 页码
    private Integer page;

    // 每页显示记录数
    private Integer pageSize;

}
