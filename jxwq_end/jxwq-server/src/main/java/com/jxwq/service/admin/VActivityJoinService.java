package com.jxwq.service.admin;


import com.baomidou.mybatisplus.extension.service.IService;
import com.jxwq.entity.VActivityJoin;

import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【v_activity_join】的数据库操作Service
 * @createDate 2024-09-09 00:31:06
 */
public interface VActivityJoinService extends IService<VActivityJoin> {

    // 根据用户id获取参与的活动id列表
    List<Map<String, Object>> getJoinActivityIdsByUserId(Integer clientUserId);

    // 根据用户id和活动id判断是否参与
    Boolean isJoin(Integer clientUserId, Integer actId);

    // 参与活动
    void joinActivity(Integer clientUserId, Integer actId);

    // 写入用户消息表
    void setClientMsg(Integer clientUserId, String msgContent);

    // 获取用户消息表
    List<Map<String, Object>> getClientMsg(Integer clientUserId);

}
