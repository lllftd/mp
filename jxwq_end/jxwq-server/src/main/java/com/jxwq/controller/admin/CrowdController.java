package com.jxwq.controller.admin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.jxwq.dto.CrowdDto;
import com.jxwq.dto.pageQuery.CrowdPageQueryDTO;
import com.jxwq.entity.Crowd;
import com.jxwq.result.AjaxResult;
import com.jxwq.result.PageResult;
import com.jxwq.service.admin.CrowdService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;
import java.util.Objects;

/**
 * @author: jxwq
 * @date: 2024/08/30
 * @description: 社群管理接口
 */
@RestController
@RequestMapping("/admin/crowd")
@Slf4j
@Api(tags = "社群管理")
public class CrowdController {

    @Resource
    private CrowdService crowdService;

    /**
     * 社群管理列表
     *
     * @return 所有社群信息
     */
    @ApiOperation("不分页查询社群")
    @GetMapping("/list")
    public AjaxResult list() {
        log.info("社群管理列表");
        LambdaQueryWrapper<Crowd> queryWrapper = new LambdaQueryWrapper<>();
        List<Crowd> list = crowdService.list(queryWrapper);
        return AjaxResult.success(list);
    }

    /**
     * 社群分页
     *
     * @param crowdPageQueryDTO 分页参数
     * @return AjaxResult
     */
    @ApiOperation("分页查询社群")
    @PostMapping("/page")
    public AjaxResult page(@RequestBody @Validated CrowdPageQueryDTO crowdPageQueryDTO) {
        Integer pageNum = crowdPageQueryDTO.getPage(); // 当前页
        Integer pageSize = crowdPageQueryDTO.getPageSize(); // 每页条数
        String crowdTitle = crowdPageQueryDTO.getCrowdTitle(); // 标题
        String crowdDescribe = crowdPageQueryDTO.getCrowdDescribe(); // 描述

        LambdaQueryWrapper<Crowd> queryWrapper = new LambdaQueryWrapper<>(); // 查询条件
        queryWrapper.orderByDesc(Crowd::getId); // 按照id倒序 (可选)
        queryWrapper.like(Objects.nonNull(crowdTitle), Crowd::getCrowdTitle, crowdTitle);
        queryWrapper.like(Objects.nonNull(crowdDescribe), Crowd::getCrowdDescribe, crowdDescribe);

        Page<Crowd> page = new Page<>(pageNum, pageSize);
        crowdService.page(page, queryWrapper); // 查询分页

        // 页码 每页多少条 总页数 总记录数 当前页数据集合
        PageResult<Crowd> pageResult = new PageResult<>(
                pageNum, pageSize, page.getPages(), page.getTotal(), page.getRecords()); // 封装分页数据

        return AjaxResult.success(pageResult);
    }

    /**
     * 社群新增修改
     *
     * @param crowdDto 社群信息
     * @return AjaxResult
     */
    @ApiOperation("新增/修改社群")
    @PostMapping("/update")
    public AjaxResult update(@RequestBody @Validated CrowdDto crowdDto) {

        Crowd crowd = new Crowd();
        BeanUtils.copyProperties(crowdDto, crowd);
        boolean result = crowdService.saveOrUpdate(crowd);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    /**
     * 社群删除
     *
     * @param id 社群id
     * @return AjaxResult
     */
    @ApiOperation("删除社群")
    @PostMapping("/delete/{id}")
    public AjaxResult delete(@PathVariable("id") Integer id) {

        boolean result = crowdService.removeById(id);
        return result ? AjaxResult.success() : AjaxResult.error();
    }
}
