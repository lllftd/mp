package com.jxwq.service.client;

import com.baomidou.mybatisplus.extension.service.IService;
import com.jxwq.dto.ClientUserLoginDto;
import com.jxwq.entity.ClientUser;

public interface ClientUserService extends IService<ClientUser> {

    /**
     * 微信登录
     *
     * @param clientUserLoginDTO 客户端用户登录DTO
     * @return 用户数据
     */
    ClientUser wxLogin(ClientUserLoginDto clientUserLoginDTO);

}
