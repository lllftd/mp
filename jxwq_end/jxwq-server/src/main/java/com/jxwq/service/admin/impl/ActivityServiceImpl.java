package com.jxwq.service.admin.impl;


import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.Activity;
import com.jxwq.mapper.ActivityMapper;
import com.jxwq.service.admin.ActivityService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * @author jxwq
 * @description 针对表【activity(活动表)】的数据库操作Service实现
 * @createDate 2024-08-31 01:06:07
 */
@Service
@Transactional(rollbackFor = Exception.class)
public class ActivityServiceImpl extends ServiceImpl<ActivityMapper, Activity> implements ActivityService {
}




