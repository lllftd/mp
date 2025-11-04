package com.jxwq.vo;

import com.jxwq.entity.ClientUser;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserLoginVo implements Serializable {

    private ClientUser user; // 用户信息

    private String token;

}
