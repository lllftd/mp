package com.jxwq.service.client.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.constant.MessageConstant;
import com.jxwq.dto.ClientUserLoginDto;
import com.jxwq.entity.ClientUser;
import com.jxwq.exception.LoginFailedException;
import com.jxwq.mapper.ClientUserMapper;
import com.jxwq.properties.WeChatProperties;
import com.jxwq.service.admin.EndCliUserService;
import com.jxwq.service.client.ClientUserService;
import com.jxwq.utils.HttpClientUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
@Transactional(rollbackFor = Exception.class)
public class ClientUserServiceImpl extends ServiceImpl<ClientUserMapper, ClientUser> implements ClientUserService {
    // 微信服务接口地址
    private static final String WX_LOGIN = "https://api.weixin.qq.com/sns/jscode2session";

    @Resource
    private WeChatProperties weChatProperties; // 微信配置
    @Resource
    private ClientUserMapper clientUserMapper;
    @Resource
    private EndCliUserService endCliUserService;

    /**
     * 微信登录
     *
     * @param clientUserLoginDTO 客户端用户登录DTO
     * @return 用户数据
     */
    public ClientUser wxLogin(ClientUserLoginDto clientUserLoginDTO) {
        String openid = getOpenid(clientUserLoginDTO.getCode());

        // 判断openid是否为空，如果为空表示登录失败，抛出业务异常
        if (openid == null) {
            throw new LoginFailedException(MessageConstant.LOGIN_FAILED);
        }

        // 判断当前用户是否为新用户
        LambdaQueryWrapper<ClientUser> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(ClientUser::getOpenId, openid);
        ClientUser clientUser = clientUserMapper.selectOne(queryWrapper);

        // 如果是新用户，自动完成注册
        if (clientUser == null) {
            ClientUser createNewUser = new ClientUser();
            createNewUser.setOpenId(openid);
            createNewUser.setNickName("微信用户" + System.currentTimeMillis());
            createNewUser.setStatus("1"); // 默认启用
            createNewUser.setGetMsg("1"); // 默认开启消息推送
            endCliUserService.save(createNewUser);

            return createNewUser;
        }

        // 返回这个用户对象
        return clientUser;
    }

    /**
     * 调用微信接口服务，获取微信用户的openid
     *
     * @param code 微信登录凭证
     * @return openid
     */
    private String getOpenid(String code) {
        // 调用微信接口服务，获得当前微信用户的openid
        Map<String, String> map = new HashMap<>();
        map.put("appid", weChatProperties.getAppid());
        map.put("secret", weChatProperties.getSecret());
        map.put("js_code", code);
        map.put("grant_type", "authorization_code");
        String json = HttpClientUtil.doGet(WX_LOGIN, map);

        JSONObject jsonObject = JSON.parseObject(json);
        if (jsonObject.containsKey("errcode")) {
            log.error("微信登录失败，错误码：{}，错误信息：{}", jsonObject.getString("errcode"), jsonObject.getString("errmsg"));
        }

        return jsonObject.getString("openid");
    }
}
