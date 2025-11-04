package com.jxwq.controller.admin;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.jxwq.dto.ActivityDto;
import com.jxwq.dto.pageQuery.ActivityPageQueryDTO;
import com.jxwq.entity.Activity;
import com.jxwq.entity.VActivityJoin;
import com.jxwq.result.AjaxResult;
import com.jxwq.result.PageResult;
import com.jxwq.service.admin.ActivityService;
import com.jxwq.service.admin.VActivityJoinService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.Date;
import java.util.List;
import java.util.Objects;

/**
 * @author: jxwq
 * @date: 2024/08/30
 * @description: 活动管理接口
 */
@RestController
@RequestMapping("/admin/activity")
@Slf4j
@Api(tags = "活动管理")
public class ActivityController {

    @Resource
    private ActivityService activityService;

    @Resource
    private VActivityJoinService vActivityJoinService;

    /**
     * 活动分页
     *
     * @param activityPageQueryDTO 分页参数
     * @return AjaxResult
     */
    @ApiOperation("分页查询活动")
    @PostMapping("/page")
    public AjaxResult page(@RequestBody @Validated ActivityPageQueryDTO activityPageQueryDTO) {
        Integer pageNum = activityPageQueryDTO.getPage(); // 当前页
        Integer pageSize = activityPageQueryDTO.getPageSize(); // 每页条数
        String actTitle = activityPageQueryDTO.getActTitle(); // 标题
        String actDescribe = activityPageQueryDTO.getActDescribe(); // 描述
        Date actStartDate = activityPageQueryDTO.getActStartDate(); // 开始时间
        Date actEndDate = activityPageQueryDTO.getActEndDate(); // 结束时间

        LambdaQueryWrapper<Activity> queryWrapper = new LambdaQueryWrapper<>(); // 查询条件
        queryWrapper.orderByDesc(Activity::getId); // 按照id倒序 (可选)
        queryWrapper.like(Objects.nonNull(actTitle), Activity::getActTitle, actTitle);
        queryWrapper.like(Objects.nonNull(actDescribe), Activity::getActDescribe, actDescribe);
        queryWrapper.between(Objects.nonNull(actStartDate), Activity::getActStartDate, actStartDate, actEndDate);

        Page<Activity> page = new Page<>(pageNum, pageSize);
        activityService.page(page, queryWrapper); // 查询分页

        // 页码 每页多少条 总页数 总记录数 当前页数据集合
        PageResult<Activity> pageResult = new PageResult<>(
                pageNum, pageSize, page.getPages(), page.getTotal(), page.getRecords()); // 封装分页数据

        return AjaxResult.success(pageResult);
    }

    /**
     * 活动新增修改
     *
     * @param activityDto 活动信息
     * @return AjaxResult
     */
    @ApiOperation("新增/修改活动")
    @PostMapping("/update")
    public AjaxResult update(@RequestBody @Validated ActivityDto activityDto) {

        Activity activity = new Activity();
        BeanUtils.copyProperties(activityDto, activity);
        boolean result = activityService.saveOrUpdate(activity);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    /**
     * 活动删除
     *
     * @param id 活动id
     * @return AjaxResult
     */
    @ApiOperation("删除活动")
    @PostMapping("/delete/{id}")
    public AjaxResult delete(@PathVariable("id") Integer id) {

        boolean result = activityService.removeById(id);
        return result ? AjaxResult.success() : AjaxResult.error();
    }

    /**
     * 查询某人参加的活动
     *
     * @param userId 用户id
     * @return AjaxResult
     */
    @ApiOperation("查询某用户参加的活动")
    @GetMapping("/joinActivity/{userId}")
    public AjaxResult getJoinActivity(@PathVariable Integer userId) {

        LambdaQueryWrapper<VActivityJoin> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.orderByDesc(VActivityJoin::getId); // 按照id倒序 (可选)
        lambdaQueryWrapper.eq(VActivityJoin::getClientUserId, userId);
        List<VActivityJoin> list = vActivityJoinService.list(lambdaQueryWrapper);
        return AjaxResult.success(list);
    }

}
