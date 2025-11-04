package com.jxwq.service.admin.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.jxwq.entity.VTweets;
import com.jxwq.mapper.VTweetsMapper;
import com.jxwq.service.admin.VTweetsService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

/**
 * @author jxwq
 * @description 针对表【tweets(推文表)】的数据库操作Service实现
 * @createDate 2024-08-31 01:32:10
 */
@Service
@Transactional(rollbackFor = Exception.class)
public class VTweetsServiceImpl extends ServiceImpl<VTweetsMapper, VTweets>
        implements VTweetsService {

    @Resource
    private VTweetsMapper vTweetsMapper;

    // 随机获取10条推文
    @Override
    public List<Map<String, Object>> randomTweets() {
        return vTweetsMapper.randomTweets();
    }
}




