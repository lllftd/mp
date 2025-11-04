package com.jxwq.controller.admin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.jxwq.constant.MessageConstant;
import com.jxwq.dto.TweetDto;
import com.jxwq.dto.TweetsTypeDto;
import com.jxwq.dto.pageQuery.TweetsPageQueryDTO;
import com.jxwq.entity.Tweets;
import com.jxwq.entity.TweetsType;
import com.jxwq.entity.VTweets;
import com.jxwq.result.AjaxResult;
import com.jxwq.result.PageResult;
import com.jxwq.service.admin.TweetsService;
import com.jxwq.service.admin.TweetsTypeService;
import com.jxwq.service.admin.VTweetsService;
import com.jxwq.vo.TweetsTreeVo;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.*;

/**
 * @author: jxwq
 * @date: 2024/08/30
 * @description: 推文管理接口
 */
@RestController
@RequestMapping("/admin/tweets")
@Slf4j
@Api(tags = "推文管理")
public class TweetsController {

    @Resource
    private TweetsService tweetsService;
    @Resource
    private VTweetsService vTweetsService;
    @Resource
    private TweetsTypeService tweetsTypeService;

    /**
     * 推文分页
     *
     * @param tweetsPageQueryDTO 分页参数
     * @return AjaxResult
     */
    @ApiOperation("分页查询推文")
    @PostMapping("/page")
    public AjaxResult page(@RequestBody @Validated TweetsPageQueryDTO tweetsPageQueryDTO) {
        Integer pageNum = tweetsPageQueryDTO.getPage(); // 当前页
        Integer pageSize = tweetsPageQueryDTO.getPageSize(); // 每页条数
        Integer tweetsTypePid = tweetsPageQueryDTO.getTweetsTypePid(); // 推文类型 一级类目

        LambdaQueryWrapper<VTweets> queryWrapper = new LambdaQueryWrapper<>(); // 查询条件
        queryWrapper.orderByDesc(Tweets::getId); // 按照id倒序 (可选)
        queryWrapper.eq(Objects.nonNull(tweetsTypePid), VTweets::getTweetsTypePid, tweetsTypePid);

        Page<VTweets> page = new Page<>(pageNum, pageSize);
        vTweetsService.page(page, queryWrapper); // 查询分页

        // 页码 每页多少条 总页数 总记录数 当前页数据集合
        PageResult<VTweets> pageResult = new PageResult<>(
                pageNum, pageSize, page.getPages(), page.getTotal(), page.getRecords()); // 封装分页数据

        return AjaxResult.success(pageResult);
    }

    /**
     * 推文新增修改
     *
     * @param tweetDto 推文信息
     * @return AjaxResult
     */
    @ApiOperation("新增/修改推文")
    @PostMapping("/update")
    public AjaxResult update(@RequestBody @Validated TweetDto tweetDto) {
        Tweets tweets = new Tweets();
        BeanUtils.copyProperties(tweetDto, tweets);
        boolean result = tweetsService.saveOrUpdate(tweets);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    /**
     * 推文删除
     *
     * @param id 推文id
     * @return AjaxResult
     */
    @ApiOperation("删除推文")
    @PostMapping("/delete/{id}")
    public AjaxResult delete(@PathVariable("id") Integer id) {
        boolean result = tweetsService.removeById(id);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    @ApiOperation("获取推文类型列表")
    @GetMapping("/tweetsType")
    public AjaxResult getTweetsTypeDict() {
        LambdaQueryWrapper<TweetsType> queryWrapper = new LambdaQueryWrapper<>();
        List<TweetsType> list = tweetsTypeService.list(queryWrapper);

        // 将查询结果转换为 TweetsTreeVo
        Map<Integer, TweetsTreeVo> nodeMap = new HashMap<>();

        for (TweetsType tweetsType : list) {
            TweetsTreeVo vo = new TweetsTreeVo();
            BeanUtils.copyProperties(tweetsType, vo);
            // 不初始化 children 为空列表，留作 null
            nodeMap.put(tweetsType.getId(), vo);
        }

        // 构建树形结构
        List<TweetsTreeVo> rootNodes = new ArrayList<>();

        for (TweetsType tweetsType : list) {
            TweetsTreeVo vo = nodeMap.get(tweetsType.getId());
            if (tweetsType.getParentId() == null) {
                rootNodes.add(vo);
            } else {
                TweetsTreeVo parent = nodeMap.get(tweetsType.getParentId());
                if (parent != null) {
                    if (parent.getChildren() == null) {
                        parent.setChildren(new ArrayList<>());
                    }
                    parent.getChildren().add(vo); // 添加 TweetsTreeVo 对象
                }
            }
        }

        return AjaxResult.success(rootNodes);
    }

    @ApiOperation("新增/修改推文类型")
    @PostMapping("/updateTweetsType")
    public AjaxResult updateTweetsType(@RequestBody @Validated TweetsTypeDto tweetsTypeDto) {
        // Integer id = tweetsTypeDto.getId();
        // if (id != null && tweetsService.typeUseCountInTweets(id) > 0) {
        //     // 会出现修改自己也提示这个的错误
        //     return AjaxResult.error("该类目已被使用，不允许修改！");
        // }

        TweetsType tweetsType = new TweetsType();
        BeanUtils.copyProperties(tweetsTypeDto, tweetsType);
        boolean result = tweetsTypeService.saveOrUpdate(tweetsType);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    @ApiOperation("删除推文类型")
    @PostMapping("/deleteTweetsType/{id}")
    public AjaxResult deleteTweetsType(@PathVariable("id") Integer id) {
        if (tweetsService.typeUseCountInTweets(id) > 0) {
            return AjaxResult.error(MessageConstant.TWEETS_TYPE_DELETE_FAILED);
        }

        boolean result = tweetsTypeService.removeById(id);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

}
