package com.jxwq.service.admin.impl;


import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.VActivityJoin;
import com.jxwq.mapper.VActivityJoinMapper;
import com.jxwq.service.admin.VActivityJoinService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【v_activity_join】的数据库操作Service实现
 * @createDate 2024-09-09 00:31:06
 */
@Transactional(rollbackFor = Exception.class)
@Service
public class VActivityJoinServiceImpl extends ServiceImpl<VActivityJoinMapper, VActivityJoin>
        implements VActivityJoinService {

    @Resource
    private VActivityJoinMapper vActivityJoinMapper;

    @Override
    public List<Map<String, Object>> getJoinActivityIdsByUserId(Integer clientUserId) {
        return vActivityJoinMapper.getJoinActivityIdsByUserId(clientUserId);
    }

    @Override
    public Boolean isJoin(Integer clientUserId, Integer actId) {
        Integer count = vActivityJoinMapper.isJoin(clientUserId, actId);
        return count > 0;
    }

    @Override
    public void joinActivity(Integer clientUserId, Integer actId) {
        vActivityJoinMapper.joinActivity(clientUserId, actId);
    }

    @Override
    public void setClientMsg(Integer clientUserId, String msgContent) {
        vActivityJoinMapper.setClientMsg(clientUserId, msgContent);
    }

    @Override
    public List<Map<String, Object>> getClientMsg(Integer clientUserId) {
        return vActivityJoinMapper.getClientMsg(clientUserId);
    }

}




