package com.jxwq.service.admin.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.SysDict;
import com.jxwq.mapper.SysDictMapper;
import com.jxwq.service.admin.SysDictService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * @author jxwq
 * @description 针对表【sys_dict(字典表)】的数据库操作Service实现
 * @createDate 2024-08-25 17:57:42
 */
@Service
@Transactional(rollbackFor = Exception.class)
public class SysDictServiceImpl extends ServiceImpl<SysDictMapper, SysDict> implements SysDictService {
}
