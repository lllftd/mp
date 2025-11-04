package com.jxwq.service.admin.impl;


import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.ClientUser;
import com.jxwq.mapper.ClientUserMapper;
import com.jxwq.service.admin.EndCliUserService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * @author jxwq
 * @description 针对表【client_user(客户端用户表)】的数据库操作Service实现
 * @createDate 2024-09-02 20:46:01
 */
@Service
@Transactional(rollbackFor = Exception.class)
public class EndCliUserServiceImpl extends ServiceImpl<ClientUserMapper, ClientUser>
        implements EndCliUserService {
}




