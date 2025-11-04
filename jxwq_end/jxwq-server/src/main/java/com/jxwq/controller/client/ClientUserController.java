package com.jxwq.controller.client;


import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.jxwq.constant.JwtClaimsConstant;
import com.jxwq.context.BaseContext;
import com.jxwq.dto.ClientUserLoginDto;
import com.jxwq.entity.ClientUser;
import com.jxwq.properties.JwtProperties;
import com.jxwq.result.AjaxResult;
import com.jxwq.service.admin.WxHandleService;
import com.jxwq.service.client.ClientUserService;
import com.jxwq.utils.HttpClientUtil;
import com.jxwq.utils.JwtUtil;
import com.jxwq.utils.StringUtils;
import com.jxwq.vo.UserLoginVo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.log4j.Log4j2;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

@RestController
@Log4j2
@Api(tags = "客户端用户管理")
@RequestMapping("/client/user")
public class ClientUserController {

    private static final String WX_MSG_SEC_CHECK_URL = "https://api.weixin.qq.com/wxa/msg_sec_check?access_token=";

    private static final String WX_MEDIA_CHECK_ASYNC_URL = "https://api.weixin.qq.com/wxa/media_check_async?access_token=";

    @Resource
    private WxHandleService wxHandleService;

    @Resource
    private ClientUserService clientUserService;

    @Resource
    private JwtProperties jwtProperties;

    /**
     * 微信用户登录
     *
     * @param clientUserLoginDTO 微信登录参数
     * @return 登录结果
     */
    @ApiOperation(value = "微信用户登录", notes = "微信用户登录接口")
    @PostMapping("/login")
    public AjaxResult login(@RequestBody ClientUserLoginDto clientUserLoginDTO) {
        // log.info("微信用户登录：{}", clientUserLoginDTO.getCode());

        // 微信登录
        ClientUser clientUser = clientUserService.wxLogin(clientUserLoginDTO);

        // 为微信用户生成jwt令牌
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.CLIENT_USER_ID, clientUser.getId());
        claims.put(JwtClaimsConstant.CLIENT_USER_NAME, clientUser.getNickName()); // 小程序用户名 取微信nickName
        String token = JwtUtil.createJWT(jwtProperties.getClientSecretKey(), jwtProperties.getClientTtl(), claims);

        UserLoginVo userLoginVO = UserLoginVo.builder()
                .user(clientUser)
                .token(token)
                .build();

        return AjaxResult.success(userLoginVO);
    }

    /**
     * 微信用户退出登录
     *
     * @return 退出结果
     */
    @ApiOperation(value = "微信用户退出登录", notes = "微信用户退出登录接口")
    @PostMapping("/logout")
    public AjaxResult logout() {
        return AjaxResult.success();
    }

    /**
     * 获取用户信息
     *
     * @param id 用户id
     */
    @ApiOperation(value = "获取用户信息")
    @GetMapping("/info/{id}")
    public AjaxResult getUserInfo(@PathVariable("id") Integer id) {
        ClientUser clientUser = clientUserService.getById(id);
        return AjaxResult.success(clientUser);
    }

    /**
     * 更改用户信息
     */
    @ApiOperation(value = "更改用户信息")
    @PostMapping("/update")
    public AjaxResult updateUserInfo(@RequestBody JSONObject jsonObject) throws IOException {
        ClientUser clientUser = jsonObject.toJavaObject(ClientUser.class); // 对应实体类

        // 做兼容 存在用户名 并且传了openid 则进行微信昵称违规检测
        if (!StringUtils.isBlank(clientUser.getNickName()) && !StringUtils.isBlank(clientUser.getOpenId())) {
            JSONObject wxMsgSecCheckResult = wxMsgSecCheck(clientUser.getNickName(), clientUser.getOpenId());
            if ("risky".equals(wxMsgSecCheckResult.getString("suggest"))) {
                return AjaxResult.error("昵称违规，请重新输入");
            }
        }

        // if (clientUser.getAvatar() != null) {
        //     JSONObject wxMediaCheckAsyncResult = wxMediaCheckAsync(clientUser.getAvatar(), clientUser.getOpenId());
        //     if ("risky".equals(wxMediaCheckAsyncResult.getString("suggest"))) {
        //         return AjaxResult.error("头像违规，请重新选择");
        //     }
        // }

        clientUser.setId(BaseContext.getCurrentUserInfo().getId()); // 从token中获取用户id

        boolean result = clientUserService.updateById(clientUser);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    public JSONObject wxMsgSecCheck(String content, String openid) throws IOException {
        // 调用微信接口服务
        Map<String, String> map = new HashMap<>();
        String accessToken = wxHandleService.getAccessToken();
        // map.put("access_token", accessToken);
        map.put("content", content);
        map.put("version", "2.0");
        // 场景枚举值（1 资料；2 评论；3 论坛；4 社交日志）
        map.put("scene", "2");
        map.put("openid", openid);

        String json = HttpClientUtil.doPost4Json(WX_MSG_SEC_CHECK_URL + accessToken, map);

        JSONObject jsonObject = JSON.parseObject(json);
        if (jsonObject.containsKey("errcode") && jsonObject.getIntValue("errcode") != 0) {
            log.error("微信文本检测失败，错误码：{}，错误信息：{}", jsonObject.getString("errcode"), jsonObject.getString("errmsg"));
        }

        return jsonObject.getJSONObject("result");
    }

    // 异步检测图片
    private JSONObject wxMediaCheckAsync(String mediaUrl, String openid) throws IOException {
        // 调用微信接口服务
        Map<String, String> map = new HashMap<>();
        String accessToken = wxHandleService.getAccessToken();
        // map.put("access_token", accessToken);
        map.put("media_url", mediaUrl);
        map.put("media_type", "1"); // 1:音频;2:图片
        map.put("version", "2");
        map.put("scene", "1");
        map.put("openid", openid);

        String json = HttpClientUtil.doPost4Json(WX_MEDIA_CHECK_ASYNC_URL + accessToken, map);

        JSONObject jsonObject = JSON.parseObject(json);
        if (jsonObject.containsKey("errcode") && jsonObject.getIntValue("errcode") != 0) {
            log.error("微信图片检测失败，错误码：{}，错误信息：{}", jsonObject.getString("errcode"), jsonObject.getString("errmsg"));
        }

        return jsonObject.getJSONObject("result");
    }

}
