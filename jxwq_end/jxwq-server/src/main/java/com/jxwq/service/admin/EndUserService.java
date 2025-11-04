package com.jxwq.service.admin;

import com.baomidou.mybatisplus.extension.service.IService;
import com.jxwq.dto.EndUserLoginDto;
import com.jxwq.entity.EndUser;

public interface EndUserService extends IService<EndUser> {

    /**
     * 后台用户登录
     *
     * @param endUserLoginDTO 登录信息
     * @return 登录成功的用户信息
     */
    EndUser login(EndUserLoginDto endUserLoginDTO);
}
