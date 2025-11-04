package com.jxwq.service.admin.impl;


import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.Crowd;
import com.jxwq.mapper.CrowdMapper;
import com.jxwq.service.admin.CrowdService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * @author jxwq
 * @description 针对表【crowd(社群表)】的数据库操作Service实现
 * @createDate 2024-08-30 01:17:15
 */
@Service
@Transactional(rollbackFor = Exception.class)
public class CrowdServiceImpl extends ServiceImpl<CrowdMapper, Crowd> implements CrowdService {

}
