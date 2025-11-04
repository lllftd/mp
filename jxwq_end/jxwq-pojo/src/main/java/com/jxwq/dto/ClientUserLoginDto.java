package com.jxwq.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * C端用户登录
 */
@Data
public class ClientUserLoginDto implements Serializable {

    private String code;

}
