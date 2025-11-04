package com.jxwq.service.admin.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.constant.MessageConstant;
import com.jxwq.constant.StatusConstant;
import com.jxwq.dto.EndUserLoginDto;
import com.jxwq.entity.EndUser;
import com.jxwq.exception.AccountLockedException;
import com.jxwq.exception.AccountNotFoundException;
import com.jxwq.exception.PasswordErrorException;
import com.jxwq.mapper.EndUserMapper;
import com.jxwq.service.admin.EndUserService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.DigestUtils;

import javax.annotation.Resource;
import java.nio.charset.StandardCharsets;
import java.util.Objects;

@Service
@Transactional(rollbackFor = Exception.class)
public class EndUserServiceImpl extends ServiceImpl<EndUserMapper, EndUser> implements EndUserService {

    @Resource
    private EndUserMapper endUserMapper;

    /**
     * 后台用户登录
     * @param endUserLoginDTO 登录信息
     * @return 登录成功的用户实体对象
     */
    public EndUser login(EndUserLoginDto endUserLoginDTO) {
        String username = endUserLoginDTO.getUsername();
        String password = endUserLoginDTO.getPassword();

        LambdaQueryWrapper<EndUser> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(EndUser::getUserName, username);

        // 1、根据用户名查询数据库中的数据
        EndUser endUser = endUserMapper.selectOne(queryWrapper);

        // 2、处理各种异常情况（用户名不存在、密码不对、账号被锁定）
        if (endUser == null) {
            // 账号不存在
            throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
        }

        // 密码比对
        // 对前端传过来的明文密码进行md5加密
        password = DigestUtils.md5DigestAsHex(password.getBytes(StandardCharsets.UTF_8));
        if (!password.equals(endUser.getPassword())) {
            // 密码错误
            throw new PasswordErrorException(MessageConstant.PASSWORD_ERROR);
        }

        if (Objects.equals(endUser.getStatus(), StatusConstant.DISABLE)) {
            // 账号被锁定
            throw new AccountLockedException(MessageConstant.ACCOUNT_LOCKED);
        }

        // 3、返回实体对象
        return endUser;
    }

}
